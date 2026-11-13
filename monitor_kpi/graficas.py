"""Gráficas del comportamiento de los KPIs en el tiempo.

Genera imágenes PNG (no requiere ventana, sirve en servidores y tareas
programadas):

* ``tendencia_TOTAL.png``: un panel por KPI con su evolución diaria. El
  último tramo (anterior -> actual) se pinta del color de la alerta.
* ``alertas_<NIVEL>.png``: un panel por KPI con alertas en ese nivel. Todos
  los grupos van en gris y los grupos con alerta se resaltan en color.
"""

from __future__ import annotations

import logging
import math
import warnings
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from monitor_kpi import config
from monitor_kpi.detector import KPI_SIN_DATOS
from monitor_kpi.kpis import COL_GRUPO, COL_REGISTROS, calcular_kpis
from monitor_kpi.modelos import Alerta, ResultadoDia, Severidad

logger = logging.getLogger(__name__)

# Paleta (validada para daltonismo en los 3 primeros colores) y estados.
COLOR_SERIE = "#2a78d6"
COLORES_GRUPOS = ("#2a78d6", "#eb6834", "#1baf7a")  # máx. 3 grupos resaltados
COLOR_CONTEXTO = "#c9c8c3"
COLOR_TEXTO = "#0b0b0b"
COLOR_TEXTO_2 = "#52514e"
COLOR_EJES = "#d6d5d0"
COLOR_FONDO = "#fcfcfb"
COLOR_SEVERIDAD = {Severidad.GRAVE: "#d03b3b", Severidad.LEVE: "#fab219"}
ICONO_SEVERIDAD = {Severidad.GRAVE: "▲ GRAVE", Severidad.LEVE: "● LEVE"}

COLUMNAS_PANEL = 4
MAX_GRUPOS_RESALTADOS = len(COLORES_GRUPOS)
MAX_PANELES = 12

DESCRIPCION_REGISTROS = "Registros del día"


def _importar_matplotlib():
    """Importa matplotlib en modo sin ventana. None si no está instalado."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
    except ImportError:
        return None
    return plt, mdates, FuncFormatter


MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


def _formato_fecha(valor: float, _pos: int) -> str:
    import matplotlib.dates as mdates

    fecha = mdates.num2date(valor)
    return f"{fecha.day:02d}-{MESES[fecha.month - 1]}"


def _formato_eje(valor: float, _pos: int) -> str:
    if abs(valor) >= 1_000_000:
        return f"{valor / 1_000_000:.1f}M"
    if abs(valor) >= 10_000:
        return f"{valor / 1_000:.1f}k"
    if abs(valor) >= 1_000:
        return f"{valor:,.0f}"
    return f"{valor:.0f}" if float(valor).is_integer() else f"{valor:.1f}"


class GeneradorGraficas:
    """Construye las gráficas de un día evaluado."""

    def __init__(
        self,
        carpeta: Path = config.CARPETA_GRAFICAS,
        dias_historia: int = config.DIAS_HISTORIA_GRAFICAS,
    ) -> None:
        self.carpeta = carpeta
        self.dias_historia = dias_historia
        modulos = _importar_matplotlib()
        if modulos is None:
            raise ImportError(
                "matplotlib no está instalado. Ejecute: pip install matplotlib"
            )
        self.plt, self.mdates, self.FuncFormatter = modulos

    # -- API pública --------------------------------------------------------
    def generar(
        self,
        datos: pd.DataFrame,
        resultado: ResultadoDia,
        niveles: Sequence[str],
    ) -> list[Path]:
        """Genera todas las gráficas del día y devuelve las rutas creadas."""
        destino = self.carpeta / resultado.fecha.isoformat()
        destino.mkdir(parents=True, exist_ok=True)
        historia = self._recortar_historia(datos, resultado.fecha)

        rutas = [self._tendencia_total(historia, resultado, destino)]
        for nivel in niveles:
            if nivel == config.NIVEL_TOTAL:
                continue
            alertas = [a for a in resultado.alertas if a.nivel == nivel]
            if alertas:
                rutas.append(self._alertas_nivel(historia, nivel, alertas, resultado, destino))
        return rutas

    # -- Gráficas -----------------------------------------------------------
    def _tendencia_total(
        self, historia: pd.DataFrame, resultado: ResultadoDia, destino: Path
    ) -> Path:
        tabla = calcular_kpis(historia, config.NIVEL_TOTAL).set_index(config.COL_FECHA)
        alertas = {
            a.kpi: a for a in resultado.alertas if a.nivel == config.NIVEL_TOTAL
        }
        kpis = list(config.KPIS)

        fig, ejes = self._crear_figura(len(kpis))
        for eje, kpi in zip(ejes, kpis):
            serie = tabla[kpi.nombre]
            self._dibujar_linea(eje, serie, COLOR_SERIE, ancho=2)
            self._marcar_tramo(eje, serie, resultado, alertas.get(kpi.nombre))
            self._titulo_panel(eje, kpi.descripcion, [alertas.get(kpi.nombre)])
            self._estilo_eje(eje)

        self._ocultar_sobrantes(ejes, len(kpis))
        titulo = f"Comportamiento diario de KPIs – TOTAL  |  Día evaluado: {resultado.fecha}"
        return self._guardar(fig, titulo, resultado, destino / "tendencia_TOTAL.png")

    def _alertas_nivel(
        self,
        historia: pd.DataFrame,
        nivel: str,
        alertas: Sequence[Alerta],
        resultado: ResultadoDia,
        destino: Path,
    ) -> Path:
        tabla = calcular_kpis(historia, nivel)
        fechas = sorted(tabla[config.COL_FECHA].unique())

        # Agrupa las alertas por KPI, en el orden de severidad ya calculado.
        por_kpi: dict[str, list[Alerta]] = {}
        for alerta in alertas:
            por_kpi.setdefault(alerta.kpi, []).append(alerta)
        kpis = list(por_kpi)[:MAX_PANELES]
        descripciones = {k.nombre: k.descripcion for k in config.KPIS}
        descripciones[KPI_SIN_DATOS] = DESCRIPCION_REGISTROS

        fig, ejes = self._crear_figura(len(kpis))
        for eje, kpi in zip(ejes, kpis):
            columna = COL_REGISTROS if kpi == KPI_SIN_DATOS else kpi
            pivote = (
                tabla.pivot(index=config.COL_FECHA, columns=COL_GRUPO, values=columna)
                .reindex(fechas)
            )
            if kpi == KPI_SIN_DATOS:
                pivote = pivote.fillna(0)  # el grupo que desaparece cae a 0

            alertas_kpi = por_kpi[kpi]
            resaltados = [a.grupo for a in alertas_kpi[:MAX_GRUPOS_RESALTADOS]]

            for grupo in pivote.columns:
                if grupo not in resaltados:
                    self._dibujar_linea(eje, pivote[grupo], COLOR_CONTEXTO, ancho=1)
            for color, grupo in zip(COLORES_GRUPOS, resaltados):
                self._dibujar_linea(eje, pivote[grupo], color, ancho=2, etiqueta=grupo)
                self._etiqueta_final(eje, pivote[grupo], grupo, color)

            restantes = len(alertas_kpi) - len(resaltados)
            if restantes > 0:
                eje.text(0.01, 0.02, f"+{restantes} grupo(s) más con alerta",
                         transform=eje.transAxes, fontsize=7, color=COLOR_TEXTO_2)
            if len(resaltados) > 1:
                eje.legend(loc="lower right", bbox_to_anchor=(1, 1.0), fontsize=7,
                           frameon=False, ncol=len(resaltados), handlelength=1.2)
            self._titulo_panel(eje, descripciones.get(kpi, kpi), alertas_kpi)
            self._estilo_eje(eje)

        self._ocultar_sobrantes(ejes, len(kpis))
        omitidos = len(por_kpi) - len(kpis)
        nota = f"  (+{omitidos} KPI(s) más en el CSV)" if omitidos > 0 else ""
        titulo = f"KPIs con alerta por {nivel}  |  Día evaluado: {resultado.fecha}{nota}"
        nombre = f"alertas_{nivel.replace('+', '_')}.png"
        leyenda = "  ·  Color = grupos con alerta, gris = demás grupos del nivel"
        return self._guardar(fig, titulo, resultado, destino / nombre, nota=leyenda)

    # -- Ayudantes de dibujo ------------------------------------------------
    def _recortar_historia(self, datos: pd.DataFrame, fecha: date) -> pd.DataFrame:
        fechas = sorted(f for f in datos[config.COL_FECHA].unique() if f <= fecha)
        incluidas = set(fechas[-self.dias_historia:])
        return datos[datos[config.COL_FECHA].isin(incluidas)]

    def _crear_figura(self, paneles: int):
        paneles = max(paneles, 1)
        columnas = min(COLUMNAS_PANEL, paneles)
        filas = math.ceil(paneles / columnas)
        fig, ejes = self.plt.subplots(
            filas, columnas, figsize=(4.4 * columnas, 2.9 * filas + 0.9),
            squeeze=False, facecolor=COLOR_FONDO,
        )
        return fig, list(ejes.flat)

    def _dibujar_linea(self, eje, serie: pd.Series, color: str, ancho: float,
                       etiqueta: str | None = None) -> None:
        serie = serie.dropna()
        if serie.empty:
            return
        x = pd.to_datetime(pd.Series(serie.index))
        eje.plot(x, serie.values, color=color, linewidth=ancho, label=etiqueta,
                 solid_capstyle="round", zorder=3 if etiqueta else 2)
        if len(serie) == 1 or etiqueta or color == COLOR_SERIE:
            eje.scatter(x.iloc[-1:], serie.values[-1:], s=28, color=color,
                        edgecolor=COLOR_FONDO, linewidth=1.5, zorder=4)

    def _marcar_tramo(self, eje, serie: pd.Series, resultado: ResultadoDia,
                      alerta: Alerta | None) -> None:
        """Pinta el tramo anterior -> actual con el color de la alerta."""
        if alerta is None or resultado.fecha_anterior is None:
            return
        tramo = serie.reindex([resultado.fecha_anterior, resultado.fecha]).dropna()
        if len(tramo) < 2:
            return
        color = COLOR_SEVERIDAD[alerta.severidad]
        x = pd.to_datetime(pd.Series(tramo.index))
        eje.plot(x, tramo.values, color=color, linewidth=2.5, zorder=5)
        eje.scatter(x.iloc[-1:], tramo.values[-1:], s=40, color=color,
                    edgecolor=COLOR_FONDO, linewidth=1.5, zorder=6)
        eje.annotate(f"{alerta.variacion:+.1f}{alerta.unidad}",
                     (x.iloc[-1], tramo.values[-1]), xytext=(-4, 8),
                     textcoords="offset points", ha="right", fontsize=8,
                     color=COLOR_TEXTO, fontweight="bold")

    def _etiqueta_final(self, eje, serie: pd.Series, grupo: str, color: str) -> None:
        serie = serie.dropna()
        if serie.empty:
            return
        texto = grupo if len(grupo) <= 18 else grupo[:17] + "…"
        eje.annotate(texto, (pd.Timestamp(serie.index[-1]), serie.values[-1]),
                     xytext=(4, 0), textcoords="offset points", fontsize=7,
                     color=COLOR_TEXTO_2, va="center")

    def _titulo_panel(self, eje, descripcion: str, alertas: Sequence[Alerta | None]) -> None:
        alertas = [a for a in alertas if a is not None]
        eje.set_title(descripcion, loc="left", fontsize=9, color=COLOR_TEXTO, pad=16)
        if not alertas:
            return
        peor = max(a.severidad for a in alertas)
        texto = ICONO_SEVERIDAD[peor]
        if len(alertas) > 1:
            texto += f"  ({len(alertas)} grupos)"
        eje.text(0, 1.02, texto, transform=eje.transAxes, fontsize=7.5,
                 fontweight="bold", color=COLOR_TEXTO,
                 bbox={"boxstyle": "round,pad=0.25", "facecolor": COLOR_SEVERIDAD[peor],
                       "edgecolor": "none"})

    def _estilo_eje(self, eje) -> None:
        eje.set_facecolor(COLOR_FONDO)
        for lado in ("top", "right"):
            eje.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            eje.spines[lado].set_color(COLOR_EJES)
        eje.grid(axis="y", color=COLOR_EJES, linewidth=0.6, alpha=0.7)
        eje.tick_params(colors=COLOR_TEXTO_2, labelsize=7, length=0)
        eje.yaxis.set_major_formatter(self.FuncFormatter(_formato_eje))
        eje.xaxis.set_major_locator(self.mdates.AutoDateLocator(maxticks=6))
        eje.xaxis.set_major_formatter(self.FuncFormatter(_formato_fecha))
        eje.margins(x=0.08)

    @staticmethod
    def _ocultar_sobrantes(ejes, usados: int) -> None:
        for eje in ejes[usados:]:
            eje.set_visible(False)

    def _guardar(self, fig, titulo: str, resultado: ResultadoDia, ruta: Path,
                 nota: str = "") -> Path:
        subtitulo = (
            f"Comparado contra {resultado.fecha_anterior}  ·  "
            f"{resultado.contar(Severidad.GRAVE)} grave(s), "
            f"{resultado.contar(Severidad.LEVE)} leve(s) en total"
            if resultado.fecha_anterior else "Sin día anterior para comparar"
        ) + nota
        alto = fig.get_figheight()
        fig.text(0.01, 1 - 0.18 / alto, titulo, ha="left", va="top", fontsize=12,
                 fontweight="bold", color=COLOR_TEXTO)
        fig.text(0.01, 1 - 0.45 / alto, subtitulo, ha="left", va="top", fontsize=9,
                 color=COLOR_TEXTO_2)
        with warnings.catch_warnings():
            # Con un solo día de datos matplotlib avisa que no puede escoger
            # el intervalo de fechas; la gráfica igual se genera bien.
            warnings.filterwarnings("ignore", message="AutoDateLocator")
            fig.tight_layout(rect=(0, 0, 1, 1 - 0.7 / alto))
            fig.savefig(ruta, dpi=130, facecolor=COLOR_FONDO)
        self.plt.close(fig)
        logger.debug("Gráfica guardada: %s", ruta)
        return ruta
