"""Agregación diaria de la data y cálculo de KPIs por grupo."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from monitor_kpi import config
from monitor_kpi.config import Calculo, DefinicionKpi

COL_GRUPO = "GRUPO"
COL_REGISTROS = "_registros"
SEPARADOR_GRUPO = " | "


def parsear_nivel(nivel: str) -> list[str]:
    """Convierte 'CANAL+UBICACION' en ['CANAL', 'UBICACION'] y valida."""
    if nivel.upper() == config.NIVEL_TOTAL:
        return []
    dimensiones = [d.strip().upper() for d in nivel.split("+") if d.strip()]
    desconocidas = set(dimensiones) - set(config.COLUMNAS_DIMENSION)
    if not dimensiones or desconocidas:
        raise ValueError(
            f"Nivel '{nivel}' inválido. Dimensiones permitidas: "
            f"{', '.join(config.COLUMNAS_DIMENSION)}"
        )
    return dimensiones


def columna_base(kpi: DefinicionKpi) -> str:
    """Nombre de la columna sobre la que se valida la base mínima."""
    if kpi.calculo is Calculo.RAZON:
        return f"_base_{kpi.nombre}"
    return kpi.nombre


def _columnas_a_sumar(kpis: Sequence[DefinicionKpi]) -> list[str]:
    columnas: set[str] = set()
    for kpi in kpis:
        if kpi.calculo is Calculo.SUMA:
            columnas.add(kpi.columna)
        elif kpi.calculo is Calculo.RAZON:
            columnas.update(kpi.numerador, kpi.restar, {kpi.denominador})
    return sorted(columnas)


def calcular_kpis(
    datos: pd.DataFrame,
    nivel: str,
    kpis: Sequence[DefinicionKpi] = config.KPIS,
) -> pd.DataFrame:
    """Agrega la data por FECHA y por las dimensiones del nivel.

    Returns:
        DataFrame con columnas FECHA, GRUPO, un valor por KPI y, para los
        KPIs de razón, su denominador en ``_base_<kpi>``.
    """
    dimensiones = parsear_nivel(nivel)
    claves = [config.COL_FECHA, *dimensiones]

    agrupado = datos.groupby(claves, sort=True, dropna=False)
    resultado = agrupado[_columnas_a_sumar(kpis)].sum()
    resultado[COL_REGISTROS] = agrupado.size()

    for kpi in kpis:
        if kpi.calculo is Calculo.SUMA:
            resultado[kpi.nombre] = resultado[kpi.columna]
        elif kpi.calculo is Calculo.UNICOS:
            resultado[kpi.nombre] = agrupado[kpi.columna].nunique()
        elif kpi.calculo is Calculo.RAZON:
            numerador = resultado[list(kpi.numerador)].sum(axis=1)
            if kpi.restar:
                numerador = numerador - resultado[list(kpi.restar)].sum(axis=1)
            denominador = resultado[kpi.denominador]
            resultado[kpi.nombre] = np.where(
                denominador > 0,
                numerador / denominador.where(denominador > 0, 1) * kpi.factor,
                np.nan,
            )
            resultado[columna_base(kpi)] = denominador

    resultado = resultado.reset_index()
    if dimensiones:
        resultado[COL_GRUPO] = (
            resultado[dimensiones].astype(str).agg(SEPARADOR_GRUPO.join, axis=1)
        )
    else:
        resultado[COL_GRUPO] = config.NIVEL_TOTAL

    columnas_salida = [config.COL_FECHA, COL_GRUPO, COL_REGISTROS] + [
        c for k in kpis for c in dict.fromkeys((k.nombre, columna_base(k)))
    ]
    return resultado[columnas_salida]
