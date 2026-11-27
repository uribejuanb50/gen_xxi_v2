import json
import shutil
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

def extraer_y_montar_correos(
    path_excel, hoja, nombre_tabla, filas, reintentos = 5
):
    wb = load_workbook(path_excel)
    ws = wb[hoja]
    tbl = ws.tables[nombre_tabla]
    min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)

    #alternar el segundo campo para que el contenido de la tabla siempre cambie
    if config.CORREOS_ALTERNAR_CAMPO and filas:
        anterior = ws.cell(min_row + 1, min_col + 1).value
        nuevo = alternar_valor(anterior)
        filas = [(fila[0], nuevo, *fila[2:]) for fila in filas]
        print(f"[Correos] ({datetime.datetime.now().timestamp()}) Segundo campo: {anterior!r} -> {nuevo!r}")

    #borramos los registros ya hechos
    for r in range(min_row + 1, max_row + 1):
        for c in range(min_col, max_col + 1):
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
            onedrive.forzar_sincronizacion(path_excel)
            return
        
        except PermissionError:
            print(f"[Correos] ({datetime.datetime.now().timestamp()}) Permiso denegado para el archivo {path_excel}")
            time.sleep(5)

    raise RuntimeError("No se pudo guardar")

    pass

def crear_copia_excel(path_excel_base, carpeta_destino=None):
    """
    Copia el Excel base (con su hoja y su tabla tal cual) a la carpeta de copias,
    con nombre único por ejecución: Alertas_GenXXI_aaaa-mm-dd-hh-mm-ss-mmm.xlsx
    El archivo base no se modifica.
    """
    base = Path(path_excel_base)
    carpeta = Path(carpeta_destino) if carpeta_destino else config.EXCEL_CARPETA_COPIAS
    carpeta.mkdir(parents=True, exist_ok=True)

    sello = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
    destino = carpeta / f"{base.stem}_{sello}{base.suffix}"

    shutil.copyfile(base, destino)  # copia completa del archivo: la tabla viaja dentro
    print(f"[Correos] ({datetime.datetime.now().timestamp()}) Copia creada: {destino}")
    return destino


def crear_y_montar_correos(
    path_excel_base, hoja, nombre_tabla, filas, carpeta_destino=None
):
    """Crea una copia nueva del Excel en la carpeta de copias y escribe las filas en ella."""
    destino = crear_copia_excel(path_excel_base, carpeta_destino)
    for i, fila in enumerate(filas, start=1):
        guardar_vista_previa(fila[2], f"{destino.stem}_fila{i}")
    extraer_y_montar_correos(destino, hoja, nombre_tabla, filas)
    return destino

