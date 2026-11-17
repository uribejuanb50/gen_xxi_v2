from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

DATA = RAIZ / "data"

BD_VIKI = DATA / "Archivos de Jhon Jairo Martinez Gonzalez - DB_VIKI"

ALERTAS = DATA / "Gerencia de Mejora continua de Procesos - data_alertas"
EXCEL_ALERTAS = r"D:\OneDrive - Comunicacion Celular S.A.- Comcel S.A\JuanUribe\proyectos\GenXXI_V2(deprecated_no_tocar\data\Gerencia de Mejora continua de Procesos - data_alertas\Alertas_GenXXI.xlsx"
DATA_CONTACTO = ALERTAS / "data_contacto.json"


#-----------Restricciones valores para el modulo correo---------------------------

IAS_DESARROLLADAS = [
    "VIKI"
]

CARGOS_VALIDOS_PRUEBA = [
    "PRACTICANTES", "PROFESIONALES"
]
CARGOS_VALIDOS = CARGOS_VALIDOS_PRUEBA

CAMPOS_VALIDOS = [
    "nombre", "correo"
]

IMPORTANCIAS_VALIDAS = [
    
]

MENSAJE_TEMPORAL = "" \
"Muy buenas tardes a todos los taggeados en este correo tin\n\n" \
"" \
"Este correo es de importancia alta ya que según los indicadores de la IA de VIKI, esta misma se ha caído\n" \
"Agradecemos la pronta respuesta, \n\n" \
"" \
"Atentamente\n\n" \
"" \
"Rodrigo de Gusmao" 
