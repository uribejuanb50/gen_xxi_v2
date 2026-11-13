"""Pruebas unitarias. Ejecutar con: python -m unittest discover -s tests -v"""

from __future__ import annotations

import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from monitor_kpi import config
from monitor_kpi.carga import ErrorDatos, cargar_datos
from monitor_kpi.config import Comparacion, Umbrales
from monitor_kpi.detector import (
    KPI_SIN_DATOS,
    DetectorDesviaciones,
    calcular_variacion,
    clasificar,
    fecha_anterior,
)
from monitor_kpi.kpis import calcular_kpis, parsear_nivel
from monitor_kpi.modelos import Severidad
from monitor_kpi.reporte import ReporteConsola

D1, D2 = date(2026, 8, 17), date(2026, 8, 18)


def _fila(fecha, canal, usuario, **metricas):
    fila = {
        config.COL_FECHA: fecha, "CANAL": canal, "GERENCIA": "G1",
        "UBICACION": "U1", "ATENCION": "A1", config.COL_USUARIO: usuario,
    }
    fila.update({c: 0 for c in config.COLUMNAS_METRICA})
    fila.update(metricas)
    return fila


def _datos(llamadas_d2: int, uso_d2: int = 1, n: int = 20) -> pd.DataFrame:
    filas = []
    for i in range(n):
        filas.append(_fila(D1, "CAV", f"u{i}", LICENCIA=1, USO_VIKI=1, LLAMADAS=10,
                           TIEMPO_ATENCION=3000))
        filas.append(_fila(D2, "CAV", f"u{i}", LICENCIA=1, USO_VIKI=uso_d2,
                           LLAMADAS=llamadas_d2, TIEMPO_ATENCION=3000))
    return pd.DataFrame(filas)


class TestFunciones(unittest.TestCase):
    def test_variacion_relativa_y_puntos(self):
        self.assertAlmostEqual(calcular_variacion(100, 80, Comparacion.RELATIVA), -20)
        self.assertAlmostEqual(calcular_variacion(60, 52, Comparacion.PUNTOS), -8)
        self.assertIsNone(calcular_variacion(0, 5, Comparacion.RELATIVA))

    def test_clasificar(self):
        u = Umbrales(leve=15, grave=30)
        self.assertIsNone(clasificar(10, u))
        self.assertIs(clasificar(15, u), Severidad.LEVE)
        self.assertIs(clasificar(45, u), Severidad.GRAVE)
        self.assertIsNone(clasificar(-50, u))  # mejora, no alerta

    def test_umbrales_invalidos(self):
        with self.assertRaises(ValueError):
            Umbrales(leve=30, grave=10)

    def test_fecha_anterior_con_huecos(self):
        fechas = [date(2026, 8, 14), date(2026, 8, 18)]
        self.assertEqual(fecha_anterior(fechas, D2), date(2026, 8, 14))
        self.assertIsNone(fecha_anterior(fechas, date(2026, 8, 14)))

    def test_parsear_nivel(self):
        self.assertEqual(parsear_nivel("total"), [])
        self.assertEqual(parsear_nivel("canal+ubicacion"), ["CANAL", "UBICACION"])
        with self.assertRaises(ValueError):
            parsear_nivel("REGION")


class TestKpis(unittest.TestCase):
    def test_razones(self):
        df = pd.DataFrame([
            _fila(D1, "CAV", "a", LICENCIA=1, USO_VIKI=1, LLAMADAS=10, TIEMPO_ATENCION=1000,
                  PROMOTOR=3, DETRACTOR=1, R_ENC_COMPLETAS=4),
            _fila(D1, "CAV", "b", LICENCIA=1, USO_VIKI=0, LLAMADAS=10, TIEMPO_ATENCION=3000),
        ])
        fila = calcular_kpis(df, "TOTAL").iloc[0]
        self.assertEqual(fila["usuarios_conectados"], 2)
        self.assertAlmostEqual(fila["adopcion_viki"], 50.0)
        self.assertAlmostEqual(fila["tmo"], 200.0)
        self.assertAlmostEqual(fila["nps"], 50.0)


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = DetectorDesviaciones()

    def _alertas(self, datos, kpi):
        res = self.detector.evaluar(datos, D2, ["TOTAL"])
        return [a for a in res.alertas if a.kpi == kpi]

    def test_sin_desviacion(self):
        self.assertEqual(self._alertas(_datos(10), "llamadas"), [])

    def test_caida_leve(self):
        (alerta,) = self._alertas(_datos(8), "llamadas")  # -20 %
        self.assertIs(alerta.severidad, Severidad.LEVE)

    def test_caida_grave(self):
        (alerta,) = self._alertas(_datos(5), "llamadas")  # -50 %
        self.assertIs(alerta.severidad, Severidad.GRAVE)

    def test_tmo_sube_es_deterioro(self):
        (alerta,) = self._alertas(_datos(5), "tmo")  # TMO pasa de 300 a 600
        self.assertIs(alerta.severidad, Severidad.GRAVE)
        self.assertGreater(alerta.variacion, 0)

    def test_tasa_en_puntos(self):
        (alerta,) = self._alertas(_datos(10, uso_d2=0), "adopcion_viki")
        self.assertIs(alerta.severidad, Severidad.GRAVE)
        self.assertEqual(alerta.unidad, "pp")

    def test_grupo_desaparece_es_grave(self):
        datos = _datos(10)
        datos = pd.concat([datos, pd.DataFrame(
            [_fila(D1, "OTRO", f"x{i}", LICENCIA=1, LLAMADAS=10) for i in range(15)]
        )])
        res = self.detector.evaluar(datos, D2, ["CANAL"])
        alertas = [a for a in res.alertas if a.grupo == "OTRO"]
        self.assertEqual(len(alertas), 1)  # una sola alerta, no una por KPI
        self.assertEqual(alertas[0].kpi, KPI_SIN_DATOS)
        self.assertIs(alertas[0].severidad, Severidad.GRAVE)

    def test_base_minima_omite_grupos_pequenos(self):
        # 3 usuarios con licencia: por debajo de la base mínima (10), la
        # caída total de adopción VIKI no debe generar alerta.
        res = self.detector.evaluar(_datos(10, uso_d2=0, n=3), D2, ["TOTAL"])
        kpis_alertados = {a.kpi for a in res.alertas}
        self.assertNotIn("adopcion_viki", kpis_alertados)
        self.assertNotIn("usuarios_viki", kpis_alertados)
        self.assertGreater(res.omitidas_base_minima, 0)

    def test_sin_dia_anterior(self):
        res = self.detector.evaluar(_datos(10), D1, ["TOTAL"])
        self.assertIsNone(res.fecha_anterior)
        self.assertEqual(res.alertas, [])

    def test_reporte_no_falla(self):
        res = self.detector.evaluar(_datos(5), D2, ["TOTAL", "CANAL"])
        buffer = io.StringIO()
        ReporteConsola(buffer, color=False).imprimir(res)
        self.assertIn("GRAVE", buffer.getvalue())


class TestCarga(unittest.TestCase):
    CABECERA = "CANAL,FECHA,GERENCIA,UBICACION,ATENCION,USUARIO_CONEX," + ",".join(
        config.COLUMNAS_METRICA) + ",ANTIGUEDAD\n"

    def test_carga_con_null_y_crlf(self):
        valores = ",".join(["1"] * len(config.COLUMNAS_METRICA))
        contenido = self.CABECERA + f"CAV,2026-08-18,G,U,A,123,{valores},NULL\r\n"
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "d.txt"
            ruta.write_text(contenido, encoding="utf-8")
            df = cargar_datos(ruta)
        self.assertEqual(df[config.COL_FECHA].iloc[0], D2)
        self.assertEqual(df["LLAMADAS"].iloc[0], 1)

    def test_columna_faltante(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "d.csv"
            ruta.write_text("CANAL,FECHA\nCAV,2026-08-18\n", encoding="utf-8")
            with self.assertRaises(ErrorDatos):
                cargar_datos(ruta)


if __name__ == "__main__":
    unittest.main()
