"""Lectura, validación y limpieza de la data fuente."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from monitor_kpi import config

logger = logging.getLogger(__name__)


class ErrorDatos(Exception):
    """La fuente no existe o no tiene la estructura esperada."""


def listar_archivos(ruta: Path) -> list[Path]:
    """Devuelve los archivos a leer: el archivo indicado o todos los
    archivos con extensión válida dentro de la carpeta."""
    if ruta.is_file():
        return [ruta]
    if ruta.is_dir():
        archivos = sorted(
            p for p in ruta.iterdir()
            if p.is_file() and p.suffix.lower() in config.EXTENSIONES_VALIDAS
        )
        if not archivos:
            raise ErrorDatos(
                f"No hay archivos {config.EXTENSIONES_VALIDAS} en '{ruta}'."
            )
        return archivos
    raise ErrorDatos(f"La ruta '{ruta}' no existe.")


def _leer_csv(archivo: Path) -> pd.DataFrame:
    """Lee un archivo probando las codificaciones configuradas."""
    ultimo_error: Exception | None = None
    for codificacion in config.CODIFICACIONES:
        try:
            df = pd.read_csv(
                archivo,
                sep=config.SEPARADOR,
                encoding=codificacion,
                dtype=str,
                na_values=list(config.VALORES_NULOS),
                keep_default_na=False,
            )
            logger.debug("Leído %s (%s): %d filas", archivo, codificacion, len(df))
            return df
        except UnicodeDecodeError as exc:
            ultimo_error = exc
    raise ErrorDatos(f"No se pudo decodificar '{archivo}': {ultimo_error}")


def _validar_columnas(df: pd.DataFrame, archivo: Path) -> None:
    requeridas = {
        config.COL_FECHA,
        config.COL_USUARIO,
        *config.COLUMNAS_DIMENSION,
        *config.COLUMNAS_METRICA,
    }
    faltantes = sorted(requeridas - set(df.columns))
    if faltantes:
        raise ErrorDatos(f"Columnas faltantes en '{archivo}': {faltantes}")


def _limpiar(df: pd.DataFrame) -> pd.DataFrame:
    """Tipifica fechas, dimensiones y métricas."""
    df = df.copy()

    df[config.COL_FECHA] = pd.to_datetime(
        df[config.COL_FECHA].str.strip(),
        format=config.FORMATO_FECHA,
        errors="coerce",
    ).dt.date
    invalidas = int(df[config.COL_FECHA].isna().sum())
    if invalidas:
        logger.warning("Se descartan %d filas con FECHA inválida.", invalidas)
        df = df.dropna(subset=[config.COL_FECHA])

    for col in config.COLUMNAS_DIMENSION:
        df[col] = df[col].fillna("SIN DATO").str.strip()

    df[config.COL_USUARIO] = df[config.COL_USUARIO].str.strip()

    for col in config.COLUMNAS_METRICA:
        numerica = pd.to_numeric(df[col], errors="coerce")
        no_numericos = int((numerica.isna() & df[col].notna()).sum())
        if no_numericos:
            logger.warning(
                "Columna %s: %d valores no numéricos tratados como 0.",
                col, no_numericos,
            )
        df[col] = numerica.fillna(0)

    return df


def cargar_datos(ruta: Path) -> pd.DataFrame:
    """Carga uno o varios archivos y devuelve un DataFrame limpio.

    Raises:
        ErrorDatos: si la ruta no existe, está vacía o falta alguna columna.
    """
    marcos = []
    for archivo in listar_archivos(ruta):
        df = _leer_csv(archivo)
        df.columns = [c.strip().upper() for c in df.columns]
        _validar_columnas(df, archivo)
        marcos.append(df)

    datos = _limpiar(pd.concat(marcos, ignore_index=True))
    if datos.empty:
        raise ErrorDatos(f"No quedaron filas válidas en '{ruta}'.")

    logger.info(
        "Datos cargados: %d filas, %d fechas (%s a %s).",
        len(datos),
        datos[config.COL_FECHA].nunique(),
        datos[config.COL_FECHA].min(),
        datos[config.COL_FECHA].max(),
    )
    return datos
