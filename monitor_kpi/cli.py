"""Punto de entrada por línea de comandos.

Ejemplos::

    python main.py                                  # último día vs anterior
    python main.py data/diario --fecha 2026-08-18   # día específico
    python main.py --niveles CANAL CANAL+UBICACION  # niveles a evaluar
    python main.py --historico --salida alertas.csv # todos los días

Código de salida: 0 sin alertas, 1 hay alertas leves, 2 hay alertas graves,
3 error de datos o parámetros. Sirve para encadenarlo con otros procesos.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from monitor_kpi import config
from monitor_kpi.carga import ErrorDatos, cargar_datos
from monitor_kpi.config import Umbrales
from monitor_kpi.detector import DetectorDesviaciones
from monitor_kpi.kpis import parsear_nivel
from monitor_kpi.reporte import ReporteConsola, exportar_csv

CODIGO_ERROR = 3
logger = logging.getLogger("monitor_kpi")


def _fecha(texto: str) -> date:
    try:
        return datetime.strptime(texto, config.FORMATO_FECHA).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Fecha '{texto}' inválida, use AAAA-MM-DD."
        ) from exc


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitor_kpi",
        description="Monitoreo diario de KPIs: compara cada día contra el "
                    "anterior y alerta desviaciones leves y graves.",
    )
    parser.add_argument(
        "ruta", nargs="?", type=Path, default=config.RUTA_DATOS_POR_DEFECTO,
        help="Archivo o carpeta con la data (default: %(default)s).",
    )
    alcance = parser.add_mutually_exclusive_group()
    alcance.add_argument("--fecha", type=_fecha, help="Día a evaluar (AAAA-MM-DD). Default: el último.")
    alcance.add_argument("--historico", action="store_true", help="Evalúa todos los días disponibles.")
    parser.add_argument(
        "--niveles", nargs="+", default=list(config.NIVELES_POR_DEFECTO),
        help="Dimensiones a evaluar además del TOTAL. Use '+' para combinar "
             "(ej. CANAL+UBICACION). Default: %(default)s.",
    )
    parser.add_argument("--leve", type=float, default=config.UMBRALES_RELATIVOS.leve,
                        help="Caída %% para alerta leve en volúmenes (default: %(default)s).")
    parser.add_argument("--grave", type=float, default=config.UMBRALES_RELATIVOS.grave,
                        help="Caída %% para alerta grave en volúmenes (default: %(default)s).")
    parser.add_argument("--leve-pp", type=float, default=config.UMBRALES_PUNTOS.leve,
                        help="Caída en puntos para alerta leve en tasas (default: %(default)s).")
    parser.add_argument("--grave-pp", type=float, default=config.UMBRALES_PUNTOS.grave,
                        help="Caída en puntos para alerta grave en tasas (default: %(default)s).")
    parser.add_argument("--max-alertas", type=int, default=40,
                        help="Máximo de alertas a mostrar por día; 0 = todas (default: %(default)s).")
    parser.add_argument("--salida", type=Path, help="Exporta las alertas a un CSV.")
    parser.add_argument("--sin-graficas", action="store_true", help="No genera las gráficas PNG.")
    parser.add_argument("--abrir", action="store_true",
                        help="Abre la carpeta de gráficas al terminar (Windows).")
    parser.add_argument("--dias-grafica", type=int, default=config.DIAS_HISTORIA_GRAFICAS,
                        help="Días de historia en las gráficas (default: %(default)s).")
    parser.add_argument("--sin-color", action="store_true", help="Desactiva los colores.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra mensajes de depuración.")
    return parser


def _configurar_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _configurar_logging(args.verbose)

    try:
        niveles = [config.NIVEL_TOTAL] + [n.upper() for n in args.niveles]
        for nivel in niveles:
            parsear_nivel(nivel)
        detector = DetectorDesviaciones(
            umbrales_relativos=Umbrales(args.leve, args.grave),
            umbrales_puntos=Umbrales(args.leve_pp, args.grave_pp),
        )
        datos = cargar_datos(args.ruta)

        if args.historico:
            resultados = detector.evaluar_historico(datos, niveles)
        else:
            fecha = args.fecha or max(datos[config.COL_FECHA])
            resultados = [detector.evaluar(datos, fecha, niveles)]
    except (ErrorDatos, ValueError) as exc:
        logger.error("%s", exc)
        return CODIGO_ERROR

    reporte = ReporteConsola(color=False if args.sin_color else None)
    limite = None if args.max_alertas == 0 else args.max_alertas
    for resultado in resultados:
        reporte.imprimir(resultado, max_alertas=limite)

    if args.salida:
        total = exportar_csv(resultados, args.salida)
        logger.info("Se exportaron %d alertas a %s", total, args.salida)

    if not args.sin_graficas and resultados:
        # En modo histórico solo se grafica el último día evaluado.
        _generar_graficas(datos, resultados[-1], niveles, args.dias_grafica, args.abrir)

    return max((r.severidad_maxima for r in resultados), default=0)


def _generar_graficas(datos, resultado, niveles, dias: int, abrir: bool) -> None:
    """Genera las gráficas sin interrumpir el monitoreo si algo falla."""
    try:
        from monitor_kpi.graficas import GeneradorGraficas

        rutas = GeneradorGraficas(dias_historia=dias).generar(datos, resultado, niveles)
    except ImportError as exc:
        logger.warning("Gráficas omitidas: %s", exc)
        return
    except Exception:  # noqa: BLE001 - una gráfica fallida no debe tumbar el monitoreo
        logger.exception("No se pudieron generar las gráficas.")
        return

    carpeta = rutas[0].parent.resolve()
    logger.info("Gráficas generadas (%d) en: %s", len(rutas), carpeta)
    for ruta in rutas:
        logger.info("  - %s", ruta.name)
    if abrir and hasattr(os, "startfile"):
        os.startfile(carpeta)  # type: ignore[attr-defined]
