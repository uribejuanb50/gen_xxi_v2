"""Estructuras de datos compartidas entre módulos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum


class Severidad(IntEnum):
    """Nivel de la alerta. El valor numérico permite ordenar y usarlo
    como código de salida del proceso (0 = sin alertas)."""

    LEVE = 1
    GRAVE = 2


@dataclass(frozen=True)
class Alerta:
    """Desviación detectada de un KPI en un grupo entre dos días."""

    fecha: date
    fecha_anterior: date
    nivel: str
    grupo: str
    kpi: str
    descripcion: str
    valor_anterior: float
    valor_actual: float
    variacion: float      # cambio con signo (actual vs anterior)
    deterioro: float      # magnitud del empeoramiento (siempre > 0)
    unidad: str           # "%" o "pp"
    severidad: Severidad


@dataclass
class ResultadoDia:
    """Resultado de comparar una fecha contra la anterior disponible."""

    fecha: date
    fecha_anterior: date | None
    alertas: list[Alerta] = field(default_factory=list)
    evaluaciones: int = 0           # pares grupo-KPI comparados
    omitidas_base_minima: int = 0   # pares descartados por bajo volumen

    @property
    def dias_de_diferencia(self) -> int | None:
        if self.fecha_anterior is None:
            return None
        return (self.fecha - self.fecha_anterior).days

    @property
    def severidad_maxima(self) -> int:
        return max((a.severidad for a in self.alertas), default=0)

    def contar(self, severidad: Severidad) -> int:
        return sum(1 for a in self.alertas if a.severidad is severidad)
