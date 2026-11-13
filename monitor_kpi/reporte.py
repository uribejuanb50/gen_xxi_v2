"""Presentación de resultados por consola y exportación a CSV."""

from __future__ import annotations

import csv
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from monitor_kpi.modelos import Alerta, ResultadoDia, Severidad

_RESET = "\033[0m"
_COLORES = {
    Severidad.GRAVE: "\033[1;97;41m",  # blanco sobre rojo
    Severidad.LEVE: "\033[1;30;43m",   # negro sobre amarillo
}
_VERDE = "\033[1;32m"
_GRIS = "\033[90m"

_ANCHOS = {"sev": 7, "nivel": 10, "grupo": 34, "kpi": 34, "ant": 12, "act": 12, "var": 10}


def _soporta_color(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR") or not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False
    if os.name == "nt":
        os.system("")  # habilita secuencias ANSI en la consola de Windows
    return True


def _recortar(texto: str, ancho: int) -> str:
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def _formato_valor(valor: float) -> str:
    if abs(valor) >= 1000 or float(valor).is_integer():
        return f"{valor:,.0f}"
    return f"{valor:,.2f}"


class ReporteConsola:
    """Imprime el resultado de cada día en la consola."""

    def __init__(self, salida: TextIO = sys.stdout, color: bool | None = None) -> None:
        self.salida = salida
        self.color = _soporta_color(salida) if color is None else color

    def _pintar(self, texto: str, codigo: str) -> str:
        return f"{codigo}{texto}{_RESET}" if self.color else texto

    def _linea(self, texto: str = "") -> None:
        print(texto, file=self.salida)

    def imprimir(self, resultado: ResultadoDia, max_alertas: int | None = None) -> None:
        self._linea("=" * 125)
        self._linea(f" MONITOREO KPI  |  Día evaluado: {resultado.fecha}")

        if resultado.fecha_anterior is None:
            self._linea(" Sin día anterior disponible: no hay contra qué comparar.")
            self._linea("=" * 125)
            return

        aviso = ""
        if resultado.dias_de_diferencia and resultado.dias_de_diferencia > 1:
            aviso = self._pintar(
                f"  (¡ojo! {resultado.dias_de_diferencia - 1} día(s) sin datos en medio)",
                _COLORES[Severidad.LEVE],
            )
        self._linea(f" Comparado contra: {resultado.fecha_anterior}{aviso}")
        self._linea(
            f" Evaluaciones: {resultado.evaluaciones}  |  "
            f"Omitidas por bajo volumen: {resultado.omitidas_base_minima}"
        )
        graves = resultado.contar(Severidad.GRAVE)
        leves = resultado.contar(Severidad.LEVE)
        self._linea(
            f" Alertas: {self._pintar(f' {graves} GRAVE ', _COLORES[Severidad.GRAVE])}  "
            f"{self._pintar(f' {leves} LEVE ', _COLORES[Severidad.LEVE])}"
        )
        self._linea("=" * 125)

        if not resultado.alertas:
            self._linea(self._pintar(" ✔ Sin desviaciones relevantes.", _VERDE))
            self._linea()
            return

        self._imprimir_tabla(resultado.alertas, max_alertas)

    def _imprimir_tabla(self, alertas: Sequence[Alerta], max_alertas: int | None) -> None:
        a = _ANCHOS
        encabezado = (
            f" {'SEV':<{a['sev']}} {'NIVEL':<{a['nivel']}} {'GRUPO':<{a['grupo']}} "
            f"{'KPI':<{a['kpi']}} {'ANTERIOR':>{a['ant']}} {'ACTUAL':>{a['act']}} "
            f"{'VARIACIÓN':>{a['var']}}"
        )
        self._linea(encabezado)
        self._linea(" " + "-" * (len(encabezado) - 1))

        mostradas = alertas if max_alertas is None else alertas[:max_alertas]
        for alerta in mostradas:
            sev = self._pintar(f"{alerta.severidad.name:<{a['sev']}}", _COLORES[alerta.severidad])
            variacion = f"{alerta.variacion:+.1f}{alerta.unidad}"
            self._linea(
                f" {sev} {_recortar(alerta.nivel, a['nivel']):<{a['nivel']}} "
                f"{_recortar(alerta.grupo, a['grupo']):<{a['grupo']}} "
                f"{_recortar(alerta.descripcion, a['kpi']):<{a['kpi']}} "
                f"{_formato_valor(alerta.valor_anterior):>{a['ant']}} "
                f"{_formato_valor(alerta.valor_actual):>{a['act']}} "
                f"{variacion:>{a['var']}}"
            )

        restantes = len(alertas) - len(mostradas)
        if restantes > 0:
            self._linea(self._pintar(
                f" ... y {restantes} alerta(s) más (use --max-alertas 0 para verlas todas"
                " o --salida para exportarlas).", _GRIS,
            ))
        self._linea()


def exportar_csv(resultados: Iterable[ResultadoDia], ruta: Path) -> int:
    """Escribe todas las alertas en un CSV. Devuelve la cantidad escrita."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    campos = list(Alerta.__dataclass_fields__)
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        for resultado in resultados:
            for alerta in resultado.alertas:
                fila = asdict(alerta)
                fila["severidad"] = alerta.severidad.name
                fila["variacion"] = round(alerta.variacion, 4)
                fila["deterioro"] = round(alerta.deterioro, 4)
                escritor.writerow(fila)
                total += 1
    return total
