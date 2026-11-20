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
    "ALTA", "MEDIA", "BAJA"
]

MENSAJE_TEMPORAL = "" \
"Muy buenas tardes a todos los taggeados en este correo tin tan tun ya lo sabe\n\n" \
"" \
"Este correo es de importancia alta ya que según los indicadores de la IA de VIKI, esta misma se ha caído\n" \
"Agradecemos la pronta respuesta, \n\n" \
"" \
"Atentamente\n\n" \
"" \
"Rodrigo de Gusmao" 


#-----------Configuración del modulo llamada_copilot---------------------------

# True  -> abre Edge y se ve todo lo que hace (úsalo la primera vez para iniciar sesión)
# False -> corre en segundo plano (headless), no se ve ninguna ventana
COPILOT_MOSTRAR_NAVEGADOR = True

COPILOT_URL = "https://copilot.cloud.microsoft/home"

# Perfil de Edge exclusivo para el robot (guarda la sesión de Microsoft entre corridas).
# No apuntar al perfil normal de Edge: si Edge está abierto, Selenium no puede usarlo.
COPILOT_PERFIL_EDGE = RAIZ / "perfil_edge_copilot"

# Ruta a msedgedriver.exe. None -> Selenium Manager lo resuelve solo.
# Si la red de la empresa bloquea la descarga, bájalo a mano y pon la ruta aquí.
COPILOT_EDGE_DRIVER = None

# Usar "Chat temporal" para no llenar el historial de Copilot con cada registro
COPILOT_CHAT_TEMPORAL = True

# Tiempos (segundos)
COPILOT_TIMEOUT_CARGA = 60          # espera de cada componente de la página
COPILOT_TIEMPO_LOGIN = 180          # con navegador visible: tiempo para iniciar sesión a mano
COPILOT_TIMEOUT_RESPUESTA = 240     # máximo esperando a que Copilot termine de responder
COPILOT_ESTABILIDAD_RESPUESTA = 4   # la respuesta debe quedar quieta este tiempo para darla por terminada
COPILOT_INTERVALO_SONDEO = 1
COPILOT_REINTENTOS = 3

# Aviso si el prompt armado supera esta longitud (Copilot corta o rechaza prompts muy largos)
COPILOT_MAX_CARACTERES = 16000

# Selectores de la interfaz (sacados del HTML de debug.txt). Si Microsoft cambia la página, se ajustan aquí.
COPILOT_SEL_CAJA_TEXTO = 'span[role="textbox"][contenteditable="true"]'
COPILOT_SEL_BOTON_ENVIAR = 'button[aria-label="Enviar"]'
COPILOT_SEL_BOTON_DETENER = 'button[aria-label*="Detener"], button[aria-label*="Stop"]'
COPILOT_SEL_CHAT_TEMPORAL = '[aria-label="Chat temporal"]'

# Carpeta donde se guardan HTML + pantallazo cuando algo falla
COPILOT_CARPETA_DEBUG = RAIZ / "debug_copilot"

# Marcas con las que Copilot debe envolver su respuesta (el módulo las busca en la página)
COPILOT_MARCA_INICIO = "%%INICIO-RESPUESTA%%"
COPILOT_MARCA_FIN = "%%FIN-RESPUESTA%%"

# Prompt base. $CONTEXTO$ = registros históricos, $REGISTRO$ = registro a analizar.
# Las marcas y el formato JSON del final NO se deben quitar: de ahí se sacan correo e importancia.
PROMPT_COPILOT = (
    "Actúas como analista del sistema de monitoreo de KPIs de las IAs de Claro (proyecto GenXXI).\n\n"
    "CONTEXTO (registros históricos de referencia):\n"
    "$CONTEXTO$\n\n"
    "REGISTRO A ANALIZAR:\n"
    "$REGISTRO$\n\n"
    "Instrucciones:\n"
    "1. Compara el registro con el contexto teniendo en cuenta el día de la semana, la hora, "
    "eventos o fechas especiales, tendencia de los últimos días y cualquier valor atípico.\n"
    "2. Define el nivel de importancia: ALTA (caída o afectación grave que requiere acción inmediata), "
    "MEDIA (comportamiento anormal que hay que revisar) o BAJA (variación menor o dentro de lo esperado).\n"
    "3. Redacta un correo formal en español, dirigido al equipo responsable, que explique la situación, "
    "los datos que la soportan y la acción sugerida. Sin asunto, solo el cuerpo, firmado como "
    "\"Sistema de Alertas GenXXI\".\n\n"
    "Responde ÚNICAMENTE con lo siguiente, sin texto antes ni después y sin bloque de código:\n"
    f"{COPILOT_MARCA_INICIO}\n"
    '{"importancia": "<ALTA|MEDIA|BAJA>", "correo": "<cuerpo del correo, saltos de línea como \\n>"}\n'
    f"{COPILOT_MARCA_FIN}"
)

# Manejo de la página predeterminada que abre la política de Edge en cada pestaña
COPILOT_DOMINIOS_COPILOT = ["copilot.cloud.microsoft", "m365.cloud.microsoft"]
COPILOT_DOMINIOS_LOGIN = ["login.microsoftonline.com", "login.microsoft.com", "login.live.com",
                          "device.login.microsoftonline.com"]
COPILOT_SEG_URL_ESTABLE = 3     # la URL debe quedarse quieta este tiempo para dar por terminada una redirección
COPILOT_SEG_CAJA_ESTABLE = 2    # la caja de texto debe seguir lista este tiempo antes de usarla
COPILOT_MAX_NAVEGACIONES = 5    # veces que se reintenta ir a Copilot si la pestaña termina en otra página
