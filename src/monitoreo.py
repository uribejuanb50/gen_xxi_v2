
import polars as pl
from pathlib import Path
from datetime import datetime
import src.config as config
import time



"""
GLOB:
Busca archivos que coincidan con un patrón determinado.
En este caso, "*.csv" busca todos los archivos que terminan en .csv.
glob() devuelve un iterador de rutas y list() lo convierte en una lista.

STAT():
Es un método de la clase Path de Python que permite consultar
información de un archivo directamente al sistema operativo.
No abre ni lee el CSV.

Atributos importantes:
- st_size: tamaño del archivo en bytes.
- st_mtime: fecha de última modificación.
- st_mtime_ns: fecha de modificación en nanosegundos.
- st_atime: fecha del último acceso.

JOIN():
Permite relacionar dos DataFrames mediante una columna en común.

Tipos utilizados:
- inner: conserva coincidencias en ambos DataFrames.
- anti: conserva registros que no tienen coincidencia en el otro DataFrame.

LIT():
pl.lit() permite agregar valores constantes a una columna.

ALIAS():
alias() permite asignar un nombre a una columna o expresión.

COL():
pl.col() permite hacer referencia a una columna dentro de una expresión.

SUFFIX:
Permite agregar un sufijo a los nombres de las columnas repetidas
cuando se realiza un JOIN.
"""


def obtener_metadatos():

    # Busco todos los archivos CSV dentro de CARPETA.
    CARPETA = Path(config.MONITOREO_CARPETA)

    # glob busca los archivos y list convierte el resultado en una lista.
    ARCHIVOS = list(CARPETA.glob("*.csv"))

    # Lista donde almacenaremos los metadatos.
    DATOS = []

    for ARCHIVO in ARCHIVOS:

        # Consultar los metadatos del archivo mediante stat().
        METADATOS = ARCHIVO.stat()

        DATOS.append({
            "nombre": ARCHIVO.name,
            "tamano_bytes": METADATOS.st_size,
            "fecha_modificacion": datetime.fromtimestamp(
                METADATOS.st_mtime
            ),
            "timestamp_ns": METADATOS.st_mtime_ns
        })

    # Convertir la lista de diccionarios en un DataFrame de Polars.
    return pl.DataFrame(
        DATOS,
        schema={
            "nombre": pl.String,
            "tamano_bytes": pl.Int64,
            "fecha_modificacion": pl.Datetime,
            "timestamp_ns": pl.Int64
        }
    )


def comparar_metadatos(DF_ACTUAL, DF_ANTERIOR):

    # 1. IDENTIFICAR ARCHIVOS NUEVOS

    # Comparo los nombres actuales con los anteriores.
    # how="anti" devuelve los archivos que están en DF_ACTUAL
    # pero no aparecen en DF_ANTERIOR.

    NUEVOS = (
        DF_ACTUAL.join(
            DF_ANTERIOR.select("nombre"),
            on="nombre",
            how="anti"
        )
        .with_columns(
            pl.lit("nuevo").alias("estado")
        )
    )

    # 2. IDENTIFICAR ARCHIVOS ELIMINADOS

    # Busco los archivos que estaban en DF_ANTERIOR
    # pero que ya no aparecen en DF_ACTUAL.

    ELIMINADOS = (
        DF_ANTERIOR.join(
            DF_ACTUAL.select("nombre"),
            on="nombre",
            how="anti"
        )
        .with_columns(
            pl.lit("eliminado").alias("estado")
        )
    )

    # 3. IDENTIFICAR ARCHIVOS QUE EXISTEN EN AMBOS REGISTROS

    # inner conserva únicamente los archivos que coinciden
    # en ambos DataFrames utilizando el nombre como referencia.

    # suffix="_anterior" diferencia las columnas repetidas.

    COMPARACION = DF_ACTUAL.join(
        DF_ANTERIOR,
        on="nombre",
        how="inner",
        suffix="_anterior"
    )

    # 4. DETECTAR MODIFICACIONES

    # pl.col() permite hacer referencia a las columnas.
    # != significa diferente.
    # | significa OR (o).

    # Detectamos modificaciones si cambia el tamaño
    # o la fecha de modificación.

    MODIFICADOS = (
        COMPARACION.filter(
            (pl.col("tamano_bytes") != pl.col("tamano_bytes_anterior")) |
            (pl.col("timestamp_ns") != pl.col("timestamp_ns_anterior"))
        )
        .select(DF_ACTUAL.columns)
        .with_columns(
            pl.lit("modificado").alias("estado")
        )
    )

    # 5. UNIFICAR LOS RESULTADOS

    # pl.concat() une los DataFrames en uno solo.

    CAMBIOS = pl.concat([
        NUEVOS,
        MODIFICADOS,
        ELIMINADOS
    ])

    return CAMBIOS

#leer el documento

def leer_documentos_cambiados(CAMBIOS):

    DOCUMENTOS = {}
    for FILA in CAMBIOS.iter_rows(named=True):
        if FILA in CAMBIOS.iter_rows(named=True):
            RUTA_ARCHIVO =(Path(config.MONITOREO_CARPETA)/FILA["nombre"]
                           )
            DOCUMENTO = pl.read_csv(RUTA_ARCHIVO)
            DOCUMENTOS[FILA["nombre"]] = DOCUMENTO
    return DOCUMENTOS



def ejecutar_monitoreo():

    print("Iniciando monitoreo continuo...")

    # Primera inspección: establecer el estado inicial
    DF_ANTERIOR = obtener_metadatos()

    print("\nEstado inicial registrado:")
    print(DF_ANTERIOR)

    while True:

        # Esperar el intervalo configurado
        print(
            f"\nPróxima inspección en "
            f"{config.INTERVALO_INSPECCION} minutos..."
        )

        time.sleep(config.INTERVALO_INSPECCION * 60)

        # Consultar los metadatos actuales
        DF_ACTUAL = obtener_metadatos()

        # Comparar con la inspección anterior
        CAMBIOS = comparar_metadatos(
            DF_ACTUAL,
            DF_ANTERIOR
        )

        if not CAMBIOS.is_empty():

            print("\n¡Se detectaron cambios!")
            print(CAMBIOS)

            # Leer los documentos nuevos o modificados
            DOCUMENTOS = leer_documentos_cambiados(CAMBIOS)

            print("\nDocumentos leídos:")

            for NOMBRE, DOCUMENTO in DOCUMENTOS.items():

                print(f"\nArchivo: {NOMBRE}")
                print(f"Dimensiones: {DOCUMENTO.shape}")
                print(f"Columnas: {DOCUMENTO.columns}")
                print("\nPrimeros registros:")
                print(DOCUMENTO.head())

        else:

            print("\nNo se detectaron cambios.")

        # Actualizar la referencia para la siguiente inspección
        DF_ANTERIOR = DF_ACTUAL

if __name__ == "__main__":

    try:
        ejecutar_monitoreo()

    except KeyboardInterrupt:
        print("\nMonitoreo detenido por el usuario.")
    