# Monitor de KPIs – gen_xxiV2

Monitoreo diario por data: compara cada día contra el día anterior disponible
y muestra por consola las desviaciones, clasificadas como **LEVE** o **GRAVE**.

## Estructura

```
gen_xxiV2/
├── main.py                      # punto de entrada
├── requirements.txt
├── monitor_kpi/
│   ├── config.py                # columnas, KPIs, umbrales (lo que se calibra)
│   ├── modelos.py               # Alerta, Severidad, ResultadoDia
│   ├── carga.py                 # lectura, validación y limpieza de la data
│   ├── kpis.py                  # agregación diaria y cálculo de KPIs por grupo
│   ├── detector.py              # comparación día vs anterior y severidad
│   ├── reporte.py               # salida por consola y export a CSV
│   └── cli.py                   # argumentos de línea de comandos
├── scripts/generar_datos_prueba.py   # data FICTICIA para pruebas
└── tests/test_monitor.py
```

## Instalación

```bash
venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py                                   # último día de data/debug vs su anterior
python main.py ruta\a\carpeta_o_archivo.txt      # otra fuente (archivo o carpeta con .txt/.csv)
python main.py --fecha 2026-08-18                # un día específico
python main.py --historico                       # todos los días (útil para calibrar umbrales)
python main.py --niveles CANAL GERENCIA CANAL+UBICACION
python main.py --leve 10 --grave 25              # umbrales de volumen (% de caída)
python main.py --leve-pp 3 --grave-pp 8          # umbrales de tasas (puntos porcentuales)
python main.py --salida salidas\alertas.csv      # exporta las alertas (no lo guarde dentro de la carpeta de datos)
```

**Código de salida:** `0` sin alertas, `1` hay leves, `2` hay graves, `3` error.
Permite encadenarlo con otros procesos (tareas programadas, nodo padre, etc.).

## Cómo decide la alerta

| Tipo de KPI | Ejemplos | Desviación | LEVE | GRAVE |
|---|---|---|---|---|
| Volumen | usuarios, licencias, sesiones, llamadas | % de caída | ≥ 15 % | ≥ 30 % |
| Tasa | % adopción VIKI, % solución | caída en puntos | ≥ 5 pp | ≥ 10 pp |
| NPS | (promotores − detractores) / encuestas | caída en puntos | ≥ 10 pp | ≥ 20 pp |
| TMO | tiempo atención / llamadas | % de **subida** | ≥ 15 % | ≥ 30 % |

- Si un grupo reportó ayer y hoy no aparece: una única alerta GRAVE "SIN REGISTROS".
- Grupos con base menor a `BASE_MINIMA_POR_DEFECTO` (10) no se evalúan, para no
  alertar por ruido.
- Si entre el día evaluado y el anterior hay días sin datos, el reporte lo advierte.
- Las mejoras nunca generan alerta.

Para agregar o quitar KPIs, o cambiar umbrales por KPI, edite `KPIS` en
`monitor_kpi/config.py`.

## Pruebas

```bash
python -m unittest discover -s tests -v
python scripts/generar_datos_prueba.py && python main.py data/prueba
```
