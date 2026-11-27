import json
import shutil
import tempfile
from pathlib import Path
import time
import datetime
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

import src.config as config
import src.onedrive as onedrive
import src.plantilla_correo as plantilla_correo


LIMITE_CELDA_EXCEL = 32767  # caracteres máximos que admite una celda de Excel


def _log(mensaje):
    print(f"[Correos] ({datetime.datetime.now().timestamp()}) {mensaje}")


def preparar_cuerpo(cuerpo, importancia="BAJA"):
    """
    Deja el cuerpo listo para la celda que lee Power Automate:
    - si no es HTML (texto plano), lo pasa por la plantilla
    - una sola línea (los saltos de línea se vuelven <br> sueltos al pasar por el flujo)
    - sin caracteres de control que Excel no acepta
    - sin pasarse del límite de la celda (si se pasa, Excel/Power Automate lo cortan y el HTML queda roto)
    """
    cuerpo = str(cuerpo or "")
    if not plantilla_correo.es_html(cuerpo):
        _log("El cuerpo no venía en HTML, se arma con la plantilla")
        cuerpo = plantilla_correo.texto_a_html(cuerpo, importancia)

    cuerpo = ILLEGAL_CHARACTERS_RE.sub("", plantilla_correo.compactar_html(cuerpo))

    if len(cuerpo) > LIMITE_CELDA_EXCEL:
        raise ValueError(
            f"El cuerpo del correo tiene {len(cuerpo)} caracteres y una celda de Excel admite "
            f"{LIMITE_CELDA_EXCEL}; quedaría cortado y el HTML llegaría roto"
        )
    return cuerpo


def guardar_vista_previa(cuerpo, nombre):
    """Guarda el HTML tal cual se escribió en el Excel, para abrirlo en el navegador y compararlo con el correo."""
    if not config.CORREO_GUARDAR_VISTA_PREVIA:
        return None
    carpeta = Path(config.CORREO_CARPETA_VISTAS)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.html"
    ruta.write_text(
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0;">{cuerpo}</body></html>',
        encoding="utf-8",
    )
    _log(f"Vista previa del correo: {ruta}")
    return ruta


def generar_mensaje_por_importancia( #entra una tanda de perfiles para mandar mensaje por importancia 
    data_perfil, #entra una tanda de perfiles
    importancia,
    mensaje #la idea es que donde aparezca $USUARIO$ se remplaza por el nombre que aparece en 
):
    #por ahora solo hay un tipo de importancai, esto vendría de parte de la IA

    correos = "; ".join(profile["correo"] for profile in data_perfil)
    cuerpo = preparar_cuerpo(mensaje, importancia or "BAJA")

    return [(correos, f"Usuarios_{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]}", cuerpo)]

def leer_encargados(
    path_encargados,
    ia_extraer,
    cargos_extraer
):
    error_msg = "Solicitud no cordina con los parametros permitidos por el algoritmo"

    with open(path_encargados, encoding="utf-8") as f:
        datos = json.load(f)

    if ia_extraer not in config.IAS_DESARROLLADAS:
        raise ValueError(f"{error_msg} error en ia_extraer llega -> {ia_extraer}")
    

    if any(cargo not in config.CARGOS_VALIDOS for cargo in cargos_extraer):
        raise ValueError(f"{error_msg} error en cargos extraer llega -> {cargos_extraer}")

    cargos_ia = datos[ia_extraer]

    responsables_a_mandar_correo = []

    for cargo in cargos_extraer:
        responsables_por_cargo = cargos_ia[cargo]

        for encargado in responsables_por_cargo:

            if not all(llave in config.CAMPOS_VALIDOS for llave in encargado):
                raise KeyError("Campos no validos imposible mandarle correo a este usuario")

            responsables_a_mandar_correo.append(encargado)

    return responsables_a_mandar_correo #[{"nombre": nombre encargado, "correo": "correo@claro.com.co"}, ...,n]

    pass

def alternar_valor(valor_anterior):
    """
    Devuelve el siguiente valor de config.CORREOS_VALORES_ALTERNOS respecto al que había
    (Usuario 1 -> Usuario 2 -> Usuario 1 ...). Sirve para que la tabla siempre cambie
    y OneDrive / Power Automate detecten la modificación aunque el resto sea igual.
    """
    valores = config.CORREOS_VALORES_ALTERNOS
    if valor_anterior in valores:
        return valores[(valores.index(valor_anterior) + 1) % len(valores)]
    return valores[0]

def normalizar_filas(filas, n_columnas=None):
    """
    Garantiza que filas sea una lista de tuplas, una por fila de la tabla.
    Si llega un texto suelto o una fila sin envolver en lista, openpyxl recorre el texto
    letra por letra y escribe un carácter por columna (el error '3 | 8 | 5 | 1 | 9...').
    - una sola fila sin lista, ej. ("correo", "Usuario", "<html>")  -> se envuelve en [ ]
    - un texto, un número o una fila que no es tupla/lista           -> error, no se escribe nada
    - una fila con distinto número de valores que columnas de la tabla -> error, no se escribe nada
    """
    if isinstance(filas, (str, bytes)) or filas is None:
        raise TypeError(f"'filas' debe ser una lista de tuplas y llegó {type(filas).__name__}: {str(filas)[:60]!r}")

    if isinstance(filas, tuple) and filas and all(isinstance(v, (str, int, float)) or v is None for v in filas):
        filas = [filas]  # pasaron una sola fila sin la lista

    filas = list(filas)
    for i, fila in enumerate(filas, start=1):
        if isinstance(fila, (str, bytes)) or not isinstance(fila, (list, tuple)):
            raise TypeError(
                f"La fila {i} debe ser una tupla (correos, usuario, cuerpo) y llegó "
                f"{type(fila).__name__}: {str(fila)[:60]!r}"
            )
        if n_columnas is not None and len(fila) != n_columnas:
            raise ValueError(f"La fila {i} trae {len(fila)} valores y la tabla tiene {n_columnas} columnas")
    return [tuple(f) for f in filas]


def columnas_tabla(path_excel, hoja, nombre_tabla):
    """Número de columnas de la tabla del Excel (para validar las filas antes de tocar nada)."""
    wb = load_workbook(path_excel)
    min_col, _, max_col, _ = range_boundaries(wb[hoja].tables[nombre_tabla].ref)
    return max_col - min_col + 1


def extraer_y_montar_correos(
    path_excel, hoja, nombre_tabla, filas, reintentos = 5, sincronizar = True
):
    wb = load_workbook(path_excel)
    ws = wb[hoja]
    tbl = ws.tables[nombre_tabla]
    min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)
    filas = normalizar_filas(filas, max_col - min_col + 1)

    #alternar el segundo campo para que el contenido de la tabla siempre cambie
    if config.CORREOS_ALTERNAR_CAMPO and filas:
        anterior = ws.cell(min_row + 1, min_col + 1).value
        nuevo = alternar_valor(anterior)
        filas = [(fila[0], nuevo, *fila[2:]) for fila in filas]
        print(f"[Correos] ({datetime.datetime.now().timestamp()}) Segundo campo: {anterior!r} -> {nuevo!r}")

    #borramos los registros ya hechos y cualquier residuo por debajo o al lado de la tabla
    for r in range(min_row + 1, max(max_row, ws.max_row) + 1):
        for c in range(min_col, max(max_col, ws.max_column) + 1):
            ws.cell(r, c).value = None
    for r in range(1, min_row + 1):  # residuos a la derecha de los encabezados
        for c in range(max_col + 1, ws.max_column + 1):
            ws.cell(r, c).value = None

    #escribir nuevos
    for i, fila in enumerate(filas, start=1):
        for j, valor in enumerate(fila):
            ws.cell(min_row + i, min_col + j, valor)

    #ajustar el rango de la tabla
    ultima = min_row + max(len(filas), 1)
    tbl.ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{ultima}"

    if tbl.autoFilter is not None:
        tbl.autoFilter.ref = tbl.ref

    #guardar sobre el mismo archivo
    for itnento in range(reintentos) :
        try:
            wb.save(path_excel)
            print(f"[Correos] ({datetime.datetime.now().timestamp()}) Archivo {path_excel} actualizado")
            if sincronizar:
                onedrive.forzar_sincronizacion(path_excel)
            return
        
        except PermissionError:
            print(f"[Correos] ({datetime.datetime.now().timestamp()}) Permiso denegado para el archivo {path_excel}")
            time.sleep(5)

    raise RuntimeError("No se pudo guardar")

    pass

def _esta_dentro(ruta, carpeta):
    """True si ruta está dentro de carpeta (o en ella)."""
    try:
        Path(ruta).resolve().relative_to(Path(carpeta).resolve())
        return True
    except ValueError:
        return False


def crear_copia_excel(path_excel_base, carpeta_destino=None):
    """
    Arma la copia COMPLETA en una carpeta temporal fuera de OneDrive y devuelve su ruta.
    Nombre único por ejecución: Alertas_GenXXI_aaaa-mm-dd-hh-mm-ss-mmm.xlsx
    El archivo base (plantilla) no se modifica.
    """
    base = Path(path_excel_base)
    sello = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
    temporal = Path(tempfile.mkdtemp(prefix="genxxi_")) / f"{base.stem}_{sello}{base.suffix}"
    shutil.copyfile(base, temporal)  # copia completa del archivo: la tabla viaja dentro
    return temporal


def crear_y_montar_correos(
    path_excel_base, hoja, nombre_tabla, filas, carpeta_destino=None
):
    """
    Escribe las filas en un Excel nuevo y lo deja en la carpeta que vigila el flujo.

    Orden (importa): validar filas -> copiar la plantilla a una carpeta TEMPORAL fuera de OneDrive
    -> escribir y guardar ahí -> mover el archivo ya terminado a la carpeta vigilada.
    Así OneDrive y Power Automate solo ven el archivo cuando ya tiene el contenido final; antes
    la copia aparecía en la carpeta con lo que tuviera la plantilla y el flujo se disparaba con eso.
    """
    base = Path(path_excel_base)
    carpeta = Path(carpeta_destino) if carpeta_destino else Path(config.EXCEL_CARPETA_COPIAS)

    if _esta_dentro(base, carpeta):
        raise RuntimeError(
            f"La plantilla {base} está dentro de la carpeta que vigila el flujo ({carpeta}). "
            "Sácala de ahí: corre  python -m src.correos crear-plantilla  y pon CARPETA_ALERTAS en local.py"
        )

    filas = normalizar_filas(filas, columnas_tabla(base, hoja, nombre_tabla))

    temporal = crear_copia_excel(base, carpeta)
    try:
        extraer_y_montar_correos(temporal, hoja, nombre_tabla, filas, sincronizar=False)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / temporal.name
        shutil.move(str(temporal), str(destino))  # aparece en OneDrive ya terminado
        _log(f"Excel listo en la carpeta del flujo: {destino}")
    finally:
        shutil.rmtree(temporal.parent, ignore_errors=True)

    onedrive.forzar_sincronizacion(destino)

    for i, fila in enumerate(filas, start=1):
        guardar_vista_previa(fila[-1], f"{destino.stem}_fila{i}")
    return destino


def crear_plantilla(origen, destino=None, hoja="HojaAlertasCorreo", nombre_tabla="TablaAlertas"):
    """
    Crea la plantilla limpia a partir de un Excel existente (por ejemplo el que está hoy en OneDrive):
    deja los encabezados y la tabla con una fila vacía, y borra cualquier dato o residuo.
    """
    destino = Path(destino or config.EXCEL_PLANTILLA)
    wb = load_workbook(origen)
    ws = wb[hoja]
    tbl = ws.tables[nombre_tabla]
    min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)

    for r in range(1, max(max_row, ws.max_row) + 1):
        for c in range(1, max(max_col, ws.max_column) + 1):
            dentro_encabezado = r == min_row and min_col <= c <= max_col
            if not dentro_encabezado:
                ws.cell(r, c).value = None

    tbl.ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{min_row + 1}"
    if tbl.autoFilter is not None:
        tbl.autoFilter.ref = tbl.ref

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    encabezados = [ws.cell(min_row, c).value for c in range(min_col, max_col + 1)]
    _log(f"Plantilla creada en {destino} con columnas {encabezados}")
    return destino


if __name__ == "__main__":
    # Desde la raíz del proyecto:
    #   python -m src.correos crear-plantilla                 -> usa el EXCEL_ALERTAS de local.py como origen
    #   python -m src.correos crear-plantilla "ruta\otro.xlsx"
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "crear-plantilla":
        origen = sys.argv[2] if len(sys.argv) >= 3 else __import__("src.local", fromlist=["x"]).EXCEL_ALERTAS
        crear_plantilla(origen)
    else:
        print("Uso: python -m src.correos crear-plantilla [ruta_excel_origen]")
