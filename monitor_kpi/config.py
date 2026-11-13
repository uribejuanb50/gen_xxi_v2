"""Configuración central: columnas de la fuente, KPIs y umbrales de alerta.

Todo lo que se quiera calibrar (umbrales, KPIs, niveles de agrupación)
se cambia aquí, sin tocar la lógica de los demás módulos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Fuente de datos
# ---------------------------------------------------------------------------
RUTA_DATOS_POR_DEFECTO = Path(r"D:\OneDrive - Comunicacion Celular S.A.- Comcel S.A\JuanUribe\proyectos\GenXXI_V2\data\nube")
EXTENSIONES_VALIDAS = (".txt", ".csv")
SEPARADOR = ","
FORMATO_FECHA = "%Y-%m-%d"  # año-mes-día, como viene en la fuente
VALORES_NULOS = ("NULL", "null", "")
CODIFICACIONES = ("utf-8-sig", "latin-1")  # se prueban en este orden

COL_FECHA = "FECHA"
COL_USUARIO = "USUARIO_CONEX"

COLUMNAS_DIMENSION = ("CANAL", "GERENCIA", "UBICACION", "ATENCION")

COLUMNAS_METRICA = (
    "LICENCIA",
    "USO_VIKI",
    "TIEMPO_ATENCION",
    "CONTEO_SESIONES_UNICAS",
    "CONTEO_SESIONES",
    "INTERACCIONES",
    "DURACION",
    "LLAMADAS",
    "SI_SOLUCION",
    "NO_SOLUCION",
    "SOL_ENC_COMPLETAS",
    "DETRACTOR",
    "NEUTRO",
    "PROMOTOR",
    "R_ENC_COMPLETAS",
)

# Niveles que se evalúan por defecto (además del TOTAL).
# Para combinar dimensiones use "+", por ejemplo "CANAL+UBICACION".
NIVELES_POR_DEFECTO = ("CANAL", "GERENCIA")
NIVEL_TOTAL = "TOTAL"

# ---------------------------------------------------------------------------
# Gráficas
# ---------------------------------------------------------------------------
CARPETA_GRAFICAS = Path("salidas/graficas")  # se crea una subcarpeta por día
DIAS_HISTORIA_GRAFICAS = 30                   # días hacia atrás que se grafican


# ---------------------------------------------------------------------------
# Definición de KPIs
# ---------------------------------------------------------------------------
class Calculo(str, Enum):
    """Cómo se agrega el KPI para un día y un grupo."""

    SUMA = "suma"          # suma de una columna
    UNICOS = "unicos"      # cantidad de valores distintos de una columna
    RAZON = "razon"        # (numerador - restar) / denominador * factor


class Comparacion(str, Enum):
    """Cómo se mide la desviación contra el día anterior."""

    RELATIVA = "relativa"  # variación porcentual (%)
    PUNTOS = "puntos"      # diferencia absoluta (pp), para tasas y NPS


class Direccion(str, Enum):
    """Qué sentido de cambio es un deterioro."""

    MAYOR_ES_MEJOR = "mayor_es_mejor"  # alerta si cae
    MENOR_ES_MEJOR = "menor_es_mejor"  # alerta si sube (ej. TMO)


@dataclass(frozen=True)
class Umbrales:
    """Deterioro mínimo (en la unidad de la comparación) para cada severidad."""

    leve: float
    grave: float

    def __post_init__(self) -> None:
        if not 0 < self.leve < self.grave:
            raise ValueError(
                f"Umbrales inválidos: se requiere 0 < leve ({self.leve}) "
                f"< grave ({self.grave})."
            )


# Umbrales generales. Un KPI puede sobrescribirlos con su propio valor.
UMBRALES_RELATIVOS = Umbrales(leve=15.0, grave=30.0)  # % de caída
UMBRALES_PUNTOS = Umbrales(leve=5.0, grave=10.0)      # puntos porcentuales

# Base mínima para evaluar: evita alertas por grupos con muy poco volumen.
# Para KPIs de razón se aplica al denominador; para el resto, al valor.
BASE_MINIMA_POR_DEFECTO = 10


@dataclass(frozen=True)
class DefinicionKpi:
    """Describe cómo calcular y evaluar un KPI."""

    nombre: str
    descripcion: str
    calculo: Calculo
    comparacion: Comparacion
    columna: str | None = None                 # para SUMA / UNICOS
    numerador: tuple[str, ...] = ()            # para RAZON
    restar: tuple[str, ...] = ()               # para RAZON (ej. NPS)
    denominador: str | None = None             # para RAZON
    factor: float = 1.0
    direccion: Direccion = Direccion.MAYOR_ES_MEJOR
    umbrales: Umbrales | None = None           # None = usar los generales
    base_minima: float = BASE_MINIMA_POR_DEFECTO

    @property
    def unidad(self) -> str:
        return "%" if self.comparacion is Comparacion.RELATIVA else "pp"

    def umbrales_efectivos(
        self, relativos: Umbrales, puntos: Umbrales
    ) -> Umbrales:
        if self.umbrales is not None:
            return self.umbrales
        return relativos if self.comparacion is Comparacion.RELATIVA else puntos


KPIS: tuple[DefinicionKpi, ...] = (
    DefinicionKpi(
        nombre="usuarios_conectados",
        descripcion="Usuarios conectados (únicos)",
        calculo=Calculo.UNICOS,
        comparacion=Comparacion.RELATIVA,
        columna=COL_USUARIO,
    ),
    DefinicionKpi(
        nombre="licencias",
        descripcion="Licencias activas",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="LICENCIA",
    ),
    DefinicionKpi(
        nombre="usuarios_viki",
        descripcion="Usuarios que usaron VIKI",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="USO_VIKI",
    ),
    DefinicionKpi(
        nombre="adopcion_viki",
        descripcion="% adopción VIKI (uso / licencias)",
        calculo=Calculo.RAZON,
        comparacion=Comparacion.PUNTOS,
        numerador=("USO_VIKI",),
        denominador="LICENCIA",
        factor=100.0,
    ),
    DefinicionKpi(
        nombre="sesiones",
        descripcion="Sesiones VIKI",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="CONTEO_SESIONES",
    ),
    DefinicionKpi(
        nombre="sesiones_unicas",
        descripcion="Sesiones únicas VIKI",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="CONTEO_SESIONES_UNICAS",
    ),
    DefinicionKpi(
        nombre="interacciones",
        descripcion="Interacciones VIKI",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="INTERACCIONES",
    ),
    DefinicionKpi(
        nombre="duracion",
        descripcion="Duración total sesiones",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="DURACION",
    ),
    DefinicionKpi(
        nombre="llamadas",
        descripcion="Llamadas atendidas",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="LLAMADAS",
    ),
    DefinicionKpi(
        nombre="tmo",
        descripcion="TMO (tiempo atención / llamada)",
        calculo=Calculo.RAZON,
        comparacion=Comparacion.RELATIVA,
        numerador=("TIEMPO_ATENCION",),
        denominador="LLAMADAS",
        direccion=Direccion.MENOR_ES_MEJOR,
    ),
    DefinicionKpi(
        nombre="tasa_solucion",
        descripcion="% solución (encuesta)",
        calculo=Calculo.RAZON,
        comparacion=Comparacion.PUNTOS,
        numerador=("SI_SOLUCION",),
        denominador="SOL_ENC_COMPLETAS",
        factor=100.0,
    ),
    DefinicionKpi(
        nombre="nps",
        descripcion="NPS (promotores - detractores)",
        calculo=Calculo.RAZON,
        comparacion=Comparacion.PUNTOS,
        numerador=("PROMOTOR",),
        restar=("DETRACTOR",),
        denominador="R_ENC_COMPLETAS",
        factor=100.0,
        umbrales=Umbrales(leve=10.0, grave=20.0),  # el NPS es más volátil
    ),
    DefinicionKpi(
        nombre="encuestas_nps",
        descripcion="Encuestas de recomendación completas",
        calculo=Calculo.SUMA,
        comparacion=Comparacion.RELATIVA,
        columna="R_ENC_COMPLETAS",
    ),
)
