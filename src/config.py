import src.local as local
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1] 

DATA = RAIZ / "data"

BD_VIKI = DATA / "Archivos de Jhon Jairo Martinez Gonzalez - DB_VIKI"

ALERTAS = DATA / "Gerencia de Mejora continua de Procesos - data_alertas"
EXCEL_ALERTAS = local.EXCEL_ALERTAS
DATA_CONTACTO = DATA / "data_contacto.json"
EXCEL_CARPETA_COPIAS= Path(EXCEL_ALERTAS).parent /"exceles"
MONITOREO_CARPETA= local.CARPETA_EXCELES


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

# Alterna el segundo campo de cada fila entre estos valores en cada escritura del Excel,
# para que la tabla siempre cambie y se dispare la sincronización / el flujo
CORREOS_ALTERNAR_CAMPO = True
CORREOS_VALORES_ALTERNOS = ["Usuario 1", "Usuario 2"]

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
INTERVALO_INSPECCION = 15

# Aviso si el prompt armado supera esta longitud (Copilot corta o rechaza prompts muy largos)
COPILOT_MAX_CARACTERES = 16000

# Selectores de la interfaz (sacados del HTML de debug.txt). Si Microsoft cambia la página, se ajustan aquí.
COPILOT_SEL_CAJA_TEXTO = 'span[role="textbox"][contenteditable="true"]'
COPILOT_SEL_BOTON_ENVIAR = 'button[aria-label="Enviar"]'
COPILOT_SEL_BOTON_DETENER = 'button[aria-label*="Detener"], button[aria-label*="Stop"]'
COPILOT_SEL_CHAT_TEMPORAL = '[aria-label="Chat temporal"]'
COPILOT_SEL_RESPUESTA = '[data-testid="markdown-reply"]'   # burbuja de respuesta de Copilot

# Carpeta donde se guardan HTML + pantallazo cuando algo falla
COPILOT_CARPETA_DEBUG = RAIZ / "debug_copilot"

# Marcas con las que Copilot debe envolver su respuesta (el módulo las busca en la página)
COPILOT_MARCA_INICIO = "%%INICIO-RESPUESTA%%"
COPILOT_MARCA_FIN = "%%FIN-RESPUESTA%%"

# Prompt base. $CONTEXTO$ = registros históricos, $REGISTRO$ = registro a analizar.
# Copilot devuelve el CONTENIDO por partes en JSON; la FORMA (colores, negrillas, secciones)
# la pone src/plantilla_correo.py. Las marcas y el formato del final NO se deben quitar.
PROMPT_COPILOT = (
    "Actúas como analista senior del sistema de monitoreo de KPIs de las IAs de Claro (proyecto GenXXI). "
    "Tu correo lo leen jefes y equipos técnicos con poco tiempo: debe entenderse en 10 segundos.\n\n"
    "CONTEXTO (registros históricos de referencia):\n"
    "$CONTEXTO$\n\n"
    "REGISTRO A ANALIZAR:\n"
    "$REGISTRO$\n\n"
    "PASO 1 - ANÁLISIS\n"
    "Compara el registro con el contexto teniendo en cuenta el día de la semana, la hora, eventos o fechas "
    "especiales, la tendencia de los últimos días y cualquier valor atípico.\n\n"
    "PASO 2 - IMPORTANCIA\n"
    "ALTA: caída o afectación grave que requiere acción inmediata. "
    "MEDIA: comportamiento anormal que hay que revisar. "
    "BAJA: variación menor o dentro de lo esperado.\n\n"
    "PASO 3 - CONTENIDO DEL CORREO\n"
    "- titulo: máximo 12 palabras. Di qué pasó, en qué sistema y cuánto. "
    "Ejemplo de estilo: 'VIKI: el NPS cayó 4 pp frente a su tendencia'.\n"
    "- resumen: 2 frases como máximo. Lo más importante primero: qué pasó, magnitud y qué tan urgente es.\n"
    "- hallazgos: de 2 a 4 viñetas cortas, cada una con un dato concreto "
    "(valor actual vs. referencia, variación, día o evento relacionado).\n"
    "- impacto: 1 o 2 frases sobre qué significa para el negocio o los clientes si no se atiende.\n"
    "- acciones: de 2 a 4 acciones concretas que empiecen con verbo en infinitivo (Revisar, Validar, Escalar...).\n\n"
    "REGLAS DE ESCRITURA\n"
    "- Español formal pero directo. Frases cortas. Nada de relleno ni frases genéricas "
    "('se recomienda realizar un análisis', 'podría estar impactando').\n"
    "- Marca en negrilla con **doble asterisco** solo las cifras y conclusiones clave: máximo 2 por campo.\n"
    "- No incluyas saludo ni firma: el sistema los agrega.\n"
    "- Usa solo datos del contexto, del registro o de estas instrucciones; no inventes cifras.\n"
    "- Dentro de los textos no uses comillas dobles; si necesitas citar algo usa comillas simples.\n\n"
    "Por favor coloca en el correo que el tema de responsabilidad es el sistema de viki, e inventate que un indicador NPS cayó puntos porcentuales entre 2 - 5\n\n"
    "FORMATO DE RESPUESTA\n"
    "Responde ÚNICAMENTE con un bloque de código que contenga exactamente esto, sin texto antes ni después:\n"
    f"{COPILOT_MARCA_INICIO}\n"
    '{"importancia": "<ALTA|MEDIA|BAJA>", "titulo": "<texto>", "resumen": "<texto>", '
    '"hallazgos": ["<texto>", "<texto>"], "impacto": "<texto>", "acciones": ["<texto>", "<texto>"]}\n'
    f"{COPILOT_MARCA_FIN}"
)

CONTEXTO_PRUEBA = "Este es un contexto de prueba, después se reemplazará con un contexto real " \
"La idea es que el registro que te voy a pasar lo coloques directamente como respuesta" \
"Es decir, dado a este contexto de prueba y el prompt inicial si te paso 'ALTA' tiene sque devolver en el formato de salida" \
"'ALTA', lo mismo con 'MEDIA' y 'BAJA'"

# Manejo de la página predeterminada que abre la política de Edge en cada pestaña
COPILOT_DOMINIOS_COPILOT = ["copilot.cloud.microsoft", "m365.cloud.microsoft"]
COPILOT_DOMINIOS_LOGIN = ["login.microsoftonline.com", "login.microsoft.com", "login.live.com",
                          "device.login.microsoftonline.com"]
COPILOT_SEG_URL_ESTABLE = 3     # la URL debe quedarse quieta este tiempo para dar por terminada una redirección
COPILOT_SEG_CAJA_ESTABLE = 2    # la caja de texto debe seguir lista este tiempo antes de usarla
COPILOT_MAX_NAVEGACIONES = 5    # veces que se reintenta ir a Copilot si la pestaña termina en otra página

#-----------Configuración del modulo onedrive---------------------------

# True -> después de guardar el Excel se reinicia OneDrive para forzar que suba el cambio
ONEDRIVE_FORZAR_SINCRONIZACION = False

# Ruta a OneDrive.exe. None -> se busca sola en %LOCALAPPDATA%\Microsoft\OneDrive y Program Files
ONEDRIVE_EXE = None

ONEDRIVE_ESPERA_ANTES = 3   # segundos tras guardar antes de reiniciar OneDrive
ONEDRIVE_TIMEOUT = 60       # máximo esperando a que el archivo se libere / OneDrive cierre o arranque

#-----------Diseño del correo (modulo plantilla_correo)---------------------------

# Color de la franja y la etiqueta según importancia (ALTA usa el rojo corporativo)
CORREO_COLORES_IMPORTANCIA = {
    "ALTA": "#FF1221",
    "MEDIA": "#F59E0B",
    "BAJA": "#16A34A",
}
CORREO_SALUDO = "Hola equipo,"
CORREO_FIRMA = "Sistema de Alertas GenXXI"
CORREO_PIE = "Gerencia de Mejora Continua de Procesos · Correo generado automáticamente a partir del monitoreo de KPIs. No responder a este mensaje."
