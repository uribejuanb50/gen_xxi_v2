"""Comparación día vs. día anterior y clasificación de desviaciones."""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from datetime import date

import pandas as pd

from monitor_kpi import config
from monitor_kpi.config import Calculo, Comparacion, DefinicionKpi, Direccion, Umbrales
from monitor_kpi.kpis import COL_GRUPO, COL_REGISTROS, calcular_kpis, columna_base
from monitor_kpi.modelos import Alerta, ResultadoDia, Severidad

logger = logging.getLogger(__name__)

KPI_SIN_DATOS = "sin_registros"


def fecha_anterior(fechas: Sequence[date], fecha: date) -> date | None:
    """Última fecha disponible estrictamente anterior a ``fecha``."""
    previas = [f for f in fechas if f < fecha]
    return max(previas) if previas else None


def calcular_variacion(
    anterior: float, actual: float, comparacion: Comparacion
) -> float | None:
    """Variación con signo. None si no se puede calcular (base cero o NaN)."""
    if any(math.isnan(v) for v in (anterior, actual)):
        return None
    if comparacion is Comparacion.PUNTOS:
        return actual - anterior
    if anterior == 0:
        return None
    return (actual - anterior) / abs(anterior) * 100.0


def clasificar(deterioro: float, umbrales: Umbrales) -> Severidad | None:
    """Asigna severidad según cuánto empeoró el KPI."""
    if deterioro >= umbrales.grave:
        return Severidad.GRAVE
    if deterioro >= umbrales.leve:
        return Severidad.LEVE
    return None


class DetectorDesviaciones:
    """Evalúa los KPIs de un día contra el día anterior disponible."""

    def __init__(
        self,
        kpis: Sequence[DefinicionKpi] = config.KPIS,
        umbrales_relativos: Umbrales = config.UMBRALES_RELATIVOS,
        umbrales_puntos: Umbrales = config.UMBRALES_PUNTOS,
    ) -> None:
        self.kpis = tuple(kpis)
        self.umbrales_relativos = umbrales_relativos
        self.umbrales_puntos = umbrales_puntos

    # -- API pública --------------------------------------------------------
    def evaluar(
        self,
        datos: pd.DataFrame,
        fecha: date,
        niveles: Sequence[str],
    ) -> ResultadoDia:
        """Compara ``fecha`` contra la fecha previa en todos los niveles."""
        fechas = sorted(datos[config.COL_FECHA].unique())
        if fecha not in fechas:
            raise ValueError(f"La fecha {fecha} no existe en los datos.")

        previa = fecha_anterior(fechas, fecha)
        resultado = ResultadoDia(fecha=fecha, fecha_anterior=previa)
        if previa is None:
            logger.info("No hay día anterior a %s para comparar.", fecha)
            return resultado

        subconjunto = datos[datos[config.COL_FECHA].isin([previa, fecha])]
        for nivel in niveles:
            tabla = calcular_kpis(subconjunto, nivel, self.kpis)
            self._evaluar_nivel(tabla, nivel, previa, fecha, resultado)

        resultado.alertas.sort(
            key=lambda a: (-a.severidad, -a.deterioro, a.nivel, a.grupo)
        )
        return resultado

    def evaluar_historico(
        self, datos: pd.DataFrame, niveles: Sequence[str]
    ) -> list[ResultadoDia]:
        """Evalúa todas las fechas que tienen un día anterior."""
        fechas = sorted(datos[config.COL_FECHA].unique())
        return [self.evaluar(datos, f, niveles) for f in fechas[1:]]

    # -- Internos -----------------------------------------------------------
    def _evaluar_nivel(
        self,
        tabla: pd.DataFrame,
        nivel: str,
        previa: date,
        fecha: date,
        resultado: ResultadoDia,
    ) -> None:
        indexada = tabla.set_index([config.COL_FECHA, COL_GRUPO])
        grupos = sorted(tabla[COL_GRUPO].unique())

        # Un grupo que existía ayer y hoy no aparece se toma como caída a 0.
        completa = indexada.reindex(
            pd.MultiIndex.from_product([[previa, fecha], grupos])
        )
        for grupo in grupos:
            ayer = completa.loc[(previa, grupo)]
            hoy = completa.loc[(fecha, grupo)]
            registros_ayer = _a_float(ayer[COL_REGISTROS], vacio=0.0)
            registros_hoy = _a_float(hoy[COL_REGISTROS], vacio=0.0)

            if registros_hoy == 0:
                # El grupo no reportó nada hoy: una sola alerta, no una por KPI.
                if registros_ayer >= config.BASE_MINIMA_POR_DEFECTO:
                    resultado.evaluaciones += 1
                    resultado.alertas.append(Alerta(
                        fecha=fecha, fecha_anterior=previa, nivel=nivel,
                        grupo=grupo, kpi=KPI_SIN_DATOS,
                        descripcion="Grupo SIN REGISTROS hoy",
                        valor_anterior=registros_ayer, valor_actual=0.0,
                        variacion=-100.0, deterioro=100.0, unidad="%",
                        severidad=Severidad.GRAVE,
                    ))
                else:
                    resultado.omitidas_base_minima += 1
                continue

            for kpi in self.kpis:
                alerta = self._evaluar_kpi(
                    kpi, ayer, hoy, nivel, grupo, previa, fecha, resultado
                )
                if alerta:
                    resultado.alertas.append(alerta)

    def _evaluar_kpi(
        self,
        kpi: DefinicionKpi,
        ayer: pd.Series,
        hoy: pd.Series,
        nivel: str,
        grupo: str,
        previa: date,
        fecha: date,
        resultado: ResultadoDia,
    ) -> Alerta | None:
        base = columna_base(kpi)
        base_ayer = _a_float(ayer[base], vacio=0.0)
        base_hoy = _a_float(hoy[base], vacio=0.0)

        # Para volúmenes basta con que ayer haya tenido base suficiente
        # (así se detecta una caída a cero). Para razones se exige en ambos.
        if base_ayer < kpi.base_minima or (
            kpi.calculo is Calculo.RAZON and base_hoy < kpi.base_minima
        ):
            resultado.omitidas_base_minima += 1
            return None

        vacio = math.nan if kpi.calculo is Calculo.RAZON else 0.0
        valor_ayer = _a_float(ayer[kpi.nombre], vacio=vacio)
        valor_hoy = _a_float(hoy[kpi.nombre], vacio=vacio)

        variacion = calcular_variacion(valor_ayer, valor_hoy, kpi.comparacion)
        if variacion is None:
            return None
        resultado.evaluaciones += 1

        signo = -1 if kpi.direccion is Direccion.MAYOR_ES_MEJOR else 1
        deterioro = signo * variacion
        umbrales = kpi.umbrales_efectivos(
            self.umbrales_relativos, self.umbrales_puntos
        )
        severidad = clasificar(deterioro, umbrales)
        if severidad is None:
            return None

        return Alerta(
            fecha=fecha,
            fecha_anterior=previa,
            nivel=nivel,
            grupo=grupo,
            kpi=kpi.nombre,
            descripcion=kpi.descripcion,
            valor_anterior=valor_ayer,
            valor_actual=valor_hoy,
            variacion=variacion,
            deterioro=deterioro,
            unidad=kpi.unidad,
            severidad=severidad,
        )


def _a_float(valor: object, vacio: float) -> float:
    """Convierte a float; NaN (grupo ausente) se reemplaza por ``vacio``."""
    if valor is None or pd.isna(valor):
        return vacio
    return float(valor)
