import time
import datetime
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter

def extraer_correos(
    path_excel, hoja, nombre_tabla, filas, reintentos = 5
):
    wb = load_workbook(path_excel)
    ws = wb[hoja]
    tbl = ws.tables[nombre_tabla]
    min_col, min_row, max_col, max_row = range_boundaries(tbl.ref)

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
            return
        
        except PermissionError:
            print(f"[Correos] ({datetime.datetime.now().timestamp()}) Permiso denegado para el archivo {path_excel}")
            time.sleep(5)

    raise RuntimeError("No se pudo guardar")

    pass