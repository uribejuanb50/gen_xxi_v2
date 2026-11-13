"""Genera data FICTICIA con la misma estructura de la fuente para probar
el monitoreo sin usar datos reales. Incluye desplomes simulados el último día.

Uso::

    python scripts/generar_datos_prueba.py --dias 5 --salida data/prueba/sintetico.csv
    python main.py data/prueba
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

ENCABEZADOS = [
    "CANAL", "FECHA", "GERENCIA", "UBICACION", "ATENCION", "USUARIO_CONEX",
    "LICENCIA", "USO_VIKI", "TIEMPO_ATENCION", "CONTEO_SESIONES_UNICAS",
    "CONTEO_SESIONES", "INTERACCIONES", "DURACION", "LLAMADAS", "SI_SOLUCION",
    "NO_SOLUCION", "SOL_ENC_COMPLETAS", "DETRACTOR", "NEUTRO", "PROMOTOR",
    "R_ENC_COMPLETAS", "ANTIGUEDAD",
]

ESTRUCTURA = [
    ("CAV", "R1-Centro", "Bogota", "CAV Bogota Centro"),
    ("CAV", "R2-Noroccidente", "Medellin", "CAV Medellin Norte"),
    ("CALLCENTER", "GERENCIA CANALES A", "COS", "SWAT"),
    ("CALLCENTER", "GERENCIA CANALES B", "BARRANQUILLA", "SOPORTE"),
]


def _fila(canal, fecha, gerencia, ubic, atencion, usuario, factor_uso, factor_llamadas):
    llamadas = max(0, int(random.gauss(20, 4) * factor_llamadas))
    uso = 1 if random.random() < 0.6 * factor_uso else 0
    sesiones = random.randint(1, 6) * uso
    enc = random.randint(0, 3)
    si_sol = random.randint(0, enc)
    r_enc = random.randint(0, 3)
    prom = random.randint(0, r_enc)
    det = random.randint(0, r_enc - prom)
    return [
        canal, fecha.isoformat(), gerencia, ubic, atencion, usuario,
        1, uso, llamadas * random.randint(350, 500), sesiones, sesiones * 2,
        sesiones * random.randint(3, 8), sesiones * random.randint(60, 300),
        llamadas, si_sol, enc - si_sol, enc, det, r_enc - prom - det, prom,
        r_enc, random.choice(["NULL", "1", "2", "3"]),
    ]


def generar(dias: int, asesores: int, inicio: date, salida: Path, semilla: int) -> None:
    random.seed(semilla)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        for d in range(dias):
            fecha = inicio + timedelta(days=d)
            ultimo = d == dias - 1
            for i, (canal, ger, ubic, aten) in enumerate(ESTRUCTURA):
                # Último día: Medellín pierde uso de VIKI (grave) y
                # BARRANQUILLA baja llamadas (leve). COS desaparece.
                if ultimo and ubic == "COS":
                    continue
                factor_uso = 0.3 if ultimo and ubic == "Medellin" else 1.0
                factor_llam = 0.8 if ultimo and ubic == "BARRANQUILLA" else 1.0
                for a in range(asesores):
                    usuario = str(46430000 + i * 1000 + a)
                    escritor.writerow(_fila(canal, fecha, ger, ubic, aten, usuario,
                                            factor_uso, factor_llam))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=5)
    parser.add_argument("--asesores", type=int, default=60, help="Asesores por ubicación.")
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 8, 14))
    parser.add_argument("--salida", type=Path, default=Path("data/prueba/sintetico.csv"))
    parser.add_argument("--semilla", type=int, default=7)
    args = parser.parse_args()
    generar(args.dias, args.asesores, args.inicio, args.salida, args.semilla)
    print(f"Data ficticia generada en {args.salida}")


if __name__ == "__main__":
    main()
