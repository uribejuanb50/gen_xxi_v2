"""
Módulo llamada_copilot

Abre Microsoft 365 Copilot en Edge con Selenium, le envía un prompt y devuelve
el correo redactado y su nivel de importancia en variables separadas.

Flujo:
    crear_driver -> abrir_copilot -> insertar_prompt -> mandar_prompt -> recibir_mensaje -> cerrar_copilot

Uso rápido:
    correo, importancia = llamar_copilot(prompt)

Varios registros con un solo navegador:
    driver = crear_driver()
    try:
        for registro in registros:
            prompt = construir_prompt(config.PROMPT_COPILOT, contexto, registro)
            correo, importancia = llamar_copilot(prompt, driver=driver)
    finally:
        cerrar_copilot(driver)
"""

import json
import re
import time
import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

import src.config as config


SEL_CAJA_TEXTO = (By.CSS_SELECTOR, config.COPILOT_SEL_CAJA_TEXTO)
SEL_BOTON_ENVIAR = (By.CSS_SELECTOR, config.COPILOT_SEL_BOTON_ENVIAR)
SEL_BOTON_DETENER = (By.CSS_SELECTOR, config.COPILOT_SEL_BOTON_DETENER)
SEL_CHAT_TEMPORAL = (By.CSS_SELECTOR, config.COPILOT_SEL_CHAT_TEMPORAL)


# ----------------------------------------------------------------------------------
# Utilidades internas
# ----------------------------------------------------------------------------------

def _log(mensaje):
    print(f"[Copilot] ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) {mensaje}")


def _sin_espacios(texto):
    return re.sub(r"\s+", "", texto or "")


def _esperar_documento(driver, timeout=None):
    """Espera a que el navegador termine de cargar el documento (readyState = complete)."""
    timeout = timeout or config.COPILOT_TIMEOUT_CARGA
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def _esperar_caja_texto(driver, timeout=None):
    """Espera a que la caja de texto de Copilot exista, sea visible y se pueda usar."""
    timeout = timeout or config.COPILOT_TIMEOUT_CARGA
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(SEL_CAJA_TEXTO))


def _texto_caja(driver):
    try:
        caja = driver.find_element(*SEL_CAJA_TEXTO)
        return caja.get_attribute("innerText") or ""
    except (WebDriverException, StaleElementReferenceException):
        return ""


def _hay_generacion_en_curso(driver):
    """True si está visible el botón de detener (Copilot sigue escribiendo)."""
    try:
        return any(b.is_displayed() for b in driver.find_elements(*SEL_BOTON_DETENER))
    except (WebDriverException, StaleElementReferenceException):
        return False


def _volcar_debug(driver, etapa):
    """Guarda HTML y pantallazo de la página para revisar qué pasó cuando algo falla."""
    try:
        carpeta = config.COPILOT_CARPETA_DEBUG
        carpeta.mkdir(parents=True, exist_ok=True)
        sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_html = carpeta / f"{sello}_{etapa}.html"
        ruta_png = carpeta / f"{sello}_{etapa}.png"
        ruta_html.write_text(
            f"<!-- URL = {driver.current_url} -->\n{driver.page_source}", encoding="utf-8"
        )
        driver.save_screenshot(str(ruta_png))
        _log(f"Debug guardado en {ruta_html}")
    except Exception as e:  # el volcado nunca debe tumbar el flujo
        _log(f"No se pudo guardar el debug: {e}")


def _extraer_respuestas(texto_pagina):
    """
    Busca en el texto de la página todos los bloques entre las marcas y devuelve
    los que son JSON válido con importancia permitida: [(correo, importancia), ...].
    El bloque de ejemplo del propio prompt queda descartado porque su importancia
    es "<ALTA|MEDIA|BAJA>", que no es un valor válido.
    """
    patron = re.escape(config.COPILOT_MARCA_INICIO) + r"(.*?)" + re.escape(config.COPILOT_MARCA_FIN)
    respuestas = []

    for bloque in re.findall(patron, texto_pagina, flags=re.DOTALL):
        inicio, fin = bloque.find("{"), bloque.rfind("}")
        if inicio == -1 or fin <= inicio:
            continue
        try:
            datos = json.loads(bloque[inicio:fin + 1], strict=False)  # strict=False acepta saltos de línea reales
        except json.JSONDecodeError:
            continue
        if not isinstance(datos, dict):
            continue

        importancia = str(datos.get("importancia", "")).strip().upper()
        correo = datos.get("correo", "")

        if importancia not in config.IMPORTANCIAS_VALIDAS:
            continue
        if not isinstance(correo, str) or not correo.strip():
            continue

        respuestas.append((correo.strip(), importancia))

    return respuestas


def _respuestas_en_pagina(driver):
    try:
        texto = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
    except WebDriverException:
        return []
    return _extraer_respuestas(texto)


# ----------------------------------------------------------------------------------
# Funciones del flujo
# ----------------------------------------------------------------------------------

def construir_prompt(plantilla, contexto, registro):
    """
    Reemplaza $CONTEXTO$ y $REGISTRO$ en la plantilla.
    contexto / registro pueden ser texto, dict, lista de dicts, etc. (lo que no sea texto se pasa a JSON).
    """
    for marcador in ("$CONTEXTO$", "$REGISTRO$"):
        if marcador not in plantilla:
            raise ValueError(f"La plantilla del prompt no tiene el marcador {marcador}")

    def a_texto(valor):
        if isinstance(valor, str):
            return valor
        return json.dumps(valor, ensure_ascii=False, default=str)

    return plantilla.replace("$CONTEXTO$", a_texto(contexto)).replace("$REGISTRO$", a_texto(registro))


def crear_driver(mostrar_navegador=None):
    """Crea el Edge de Selenium. Visible o en segundo plano según config.COPILOT_MOSTRAR_NAVEGADOR."""
    if mostrar_navegador is None:
        mostrar_navegador = config.COPILOT_MOSTRAR_NAVEGADOR

    config.COPILOT_PERFIL_EDGE.mkdir(parents=True, exist_ok=True)

    opciones = Options()
    opciones.add_argument(f"--user-data-dir={config.COPILOT_PERFIL_EDGE}")
    opciones.add_argument("--profile-directory=Default")
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument("--disable-notifications")
    opciones.add_argument("--no-first-run")
    opciones.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])

    if not mostrar_navegador:
        opciones.add_argument("--headless=new")
        opciones.add_argument("--disable-gpu")

    servicio = Service(config.COPILOT_EDGE_DRIVER) if config.COPILOT_EDGE_DRIVER else Service()
    driver = webdriver.Edge(service=servicio, options=opciones)
    driver.mostrar_navegador = mostrar_navegador  # lo usa abrir_copilot para saber cuánto esperar el login

    if not mostrar_navegador:
        # En headless el user-agent dice "HeadlessEdg"; algunas páginas de Microsoft lo rechazan.
        try:
            agente = driver.execute_script("return navigator.userAgent").replace("Headless", "")
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": agente})
        except WebDriverException:
            pass

    _log(f"Edge iniciado ({'visible' if mostrar_navegador else 'segundo plano'})")
    return driver


def activar_chat_temporal(driver):
    """Activa 'Chat temporal' para no guardar la conversación en el historial. Si falla, sigue igual."""
    try:
        boton = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(SEL_CHAT_TEMPORAL))
        ya_activo = "true" in (
            (boton.get_attribute("aria-pressed") or "") + (boton.get_attribute("aria-checked") or "")
        )
        if not ya_activo:
            boton.click()
            _esperar_caja_texto(driver)
            _log("Chat temporal activado")
    except (TimeoutException, WebDriverException) as e:
        _log(f"No se pudo activar el chat temporal, se continúa en chat normal ({type(e).__name__})")


def abrir_copilot(driver):
    """
    Navega a Copilot y espera a que la caja de texto esté lista.
    También sirve para empezar una conversación nueva con el mismo navegador.
    """
    _log("Abriendo Copilot...")
    driver.get(config.COPILOT_URL)
    _esperar_documento(driver)

    visible = getattr(driver, "mostrar_navegador", config.COPILOT_MOSTRAR_NAVEGADOR)
    espera = config.COPILOT_TIEMPO_LOGIN if visible else config.COPILOT_TIMEOUT_CARGA

    try:
        _esperar_caja_texto(driver, espera)
    except TimeoutException:
        _volcar_debug(driver, "abrir_copilot")
        raise RuntimeError(
            "Copilot no cargó la caja de texto. Lo más probable es que la sesión no esté iniciada: "
            "corre una vez con COPILOT_MOSTRAR_NAVEGADOR = True e inicia sesión en la ventana."
        )

    if config.COPILOT_CHAT_TEMPORAL:
        activar_chat_temporal(driver)

    _log("Copilot listo")


def insertar_prompt(driver, prompt):
    """Escribe el prompt en la caja de texto de Copilot y verifica que quedó completo."""
    if len(prompt) > config.COPILOT_MAX_CARACTERES:
        _log(f"OJO: el prompt tiene {len(prompt)} caracteres (límite configurado {config.COPILOT_MAX_CARACTERES})")

    caja = _esperar_caja_texto(driver)
    caja.click()
    caja.send_keys(Keys.CONTROL, "a")
    caja.send_keys(Keys.DELETE)

    # Método 1: insertText (rápido, respeta saltos de línea y no dispara el envío con Enter)
    driver.execute_script(
        "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);", caja, prompt
    )

    objetivo = len(_sin_espacios(prompt))
    try:
        WebDriverWait(driver, 10).until(lambda d: len(_sin_espacios(_texto_caja(d))) >= objetivo * 0.98)
    except TimeoutException:
        # Método 2: tecleo línea por línea con Shift+Enter (más lento pero seguro)
        _log("insertText no dejó el prompt completo, se escribe línea por línea")
        caja = _esperar_caja_texto(driver)
        caja.click()
        caja.send_keys(Keys.CONTROL, "a")
        caja.send_keys(Keys.DELETE)
        lineas = prompt.split("\n")
        for i, linea in enumerate(lineas):
            if linea:
                caja.send_keys(linea)
            if i < len(lineas) - 1:
                caja.send_keys(Keys.SHIFT, Keys.ENTER)

        try:
            WebDriverWait(driver, 15).until(lambda d: len(_sin_espacios(_texto_caja(d))) >= objetivo * 0.98)
        except TimeoutException:
            _volcar_debug(driver, "insertar_prompt")
            raise RuntimeError("No se pudo escribir el prompt completo en Copilot")

    _log(f"Prompt insertado ({len(prompt)} caracteres)")


def mandar_prompt(driver):
    """
    Espera a que el botón Enviar se habilite, lo presiona y confirma que el mensaje salió.
    Devuelve cuántas respuestas válidas había antes de enviar (lo usa recibir_mensaje).
    """
    respuestas_previas = len(_respuestas_en_pagina(driver))

    try:
        boton = WebDriverWait(driver, config.COPILOT_TIMEOUT_CARGA).until(
            lambda d: next(
                (b for b in d.find_elements(*SEL_BOTON_ENVIAR)
                 if b.is_displayed() and b.get_attribute("aria-disabled") != "true"),
                False,
            )
        )
        try:
            boton.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            driver.execute_script("arguments[0].click();", boton)
    except TimeoutException:
        _log("El botón Enviar no se habilitó, se intenta con Enter")
        _esperar_caja_texto(driver).send_keys(Keys.ENTER)

    # Confirmación: la caja se vacía cuando Copilot recibe el mensaje
    try:
        WebDriverWait(driver, 20).until(lambda d: not _sin_espacios(_texto_caja(d)))
    except TimeoutException:
        _volcar_debug(driver, "mandar_prompt")
        raise RuntimeError("El prompt no se envió (la caja de texto sigue llena)")

    _log("Prompt enviado, esperando respuesta...")
    return respuestas_previas


def recibir_mensaje(driver, respuestas_previas=0):
    """
    Espera la respuesta de Copilot y devuelve (correo, importancia).
    Se da por terminada cuando aparece un bloque válido entre las marcas, Copilot dejó de
    generar y el contenido no cambia durante COPILOT_ESTABILIDAD_RESPUESTA segundos.
    """
    limite = time.time() + config.COPILOT_TIMEOUT_RESPUESTA
    ultima = None
    desde = None

    while time.time() < limite:
        respuestas = _respuestas_en_pagina(driver)

        if len(respuestas) > respuestas_previas and not _hay_generacion_en_curso(driver):
            actual = respuestas[-1]
            if actual != ultima:
                ultima, desde = actual, time.time()
            elif time.time() - desde >= config.COPILOT_ESTABILIDAD_RESPUESTA:
                correo, importancia = actual
                _log(f"Respuesta recibida (importancia {importancia}, {len(correo)} caracteres)")
                return correo, importancia
        else:
            ultima, desde = None, None

        time.sleep(config.COPILOT_INTERVALO_SONDEO)

    _volcar_debug(driver, "recibir_mensaje")
    raise TimeoutError(
        f"Copilot no devolvió una respuesta válida en {config.COPILOT_TIMEOUT_RESPUESTA} s "
        "(revisa que siga el formato con las marcas en el prompt)"
    )


def cerrar_copilot(driver):
    try:
        driver.quit()
        _log("Edge cerrado")
    except WebDriverException:
        pass


# ----------------------------------------------------------------------------------
# Función principal
# ----------------------------------------------------------------------------------

def llamar_copilot(prompt, driver=None, reintentos=None):
    """
    Envía el prompt a Copilot y devuelve (correo, importancia).
    Si no se pasa driver, abre y cierra su propio Edge.
    Cada intento abre una conversación nueva para no mezclar registros.
    """
    reintentos = reintentos or config.COPILOT_REINTENTOS
    driver_propio = driver is None
    if driver_propio:
        driver = crear_driver()

    try:
        ultimo_error = None
        for intento in range(1, reintentos + 1):
            try:
                abrir_copilot(driver)
                insertar_prompt(driver, prompt)
                previas = mandar_prompt(driver)
                return recibir_mensaje(driver, previas)
            except (RuntimeError, TimeoutError, TimeoutException, WebDriverException) as e:
                ultimo_error = e
                _log(f"Intento {intento}/{reintentos} falló: {e}")
                time.sleep(3)

        raise RuntimeError(f"Copilot no respondió después de {reintentos} intentos") from ultimo_error
    finally:
        if driver_propio:
            cerrar_copilot(driver)


if __name__ == "__main__":
    # Prueba rápida desde la raíz del proyecto:  python -m src.llamada_copilot
    contexto_prueba = [
        {"fecha": "2026-11-17", "dia": "lunes", "ia": "VIKI", "disponibilidad": 99.8, "conversaciones": 15230},
        {"fecha": "2026-11-18", "dia": "martes", "ia": "VIKI", "disponibilidad": 99.7, "conversaciones": 14980},
        {"fecha": "2026-11-19", "dia": "miércoles", "ia": "VIKI", "disponibilidad": 99.9, "conversaciones": 15410},
    ]
    registro_prueba = {"fecha": "2026-11-20", "dia": "jueves", "ia": "VIKI", "disponibilidad": 62.4, "conversaciones": 4120}

    prompt = construir_prompt(config.PROMPT_COPILOT, contexto_prueba, registro_prueba)
    correo, importancia = llamar_copilot(prompt)

    print("\nIMPORTANCIA:", importancia)
    print("CORREO:\n", correo)
