"""
Módulo onedrive

Fuerza la sincronización de OneDrive (incluye bibliotecas de SharePoint sincronizadas)
después de que Python modifica un archivo. Lo hace reiniciando el cliente de OneDrive,
que al arrancar revisa y sube los cambios pendientes. No necesita permisos de administrador.

Flujo:
    esperar_archivo_libre -> cerrar_onedrive -> iniciar_onedrive

Uso:
    import src.onedrive as onedrive
    onedrive.forzar_sincronizacion(ruta_del_excel)
"""

import os
import time
import datetime
import subprocess
from pathlib import Path

import src.config as config


def _log(mensaje):
    print(f"[OneDrive] ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) {mensaje}")


def ubicar_onedrive():
    """Busca OneDrive.exe: primero la ruta del config, luego las ubicaciones de instalación normales."""
    if config.ONEDRIVE_EXE:
        candidatos = [Path(config.ONEDRIVE_EXE)]
    else:
        candidatos = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "OneDrive" / "OneDrive.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft OneDrive" / "OneDrive.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft OneDrive" / "OneDrive.exe",
        ]

    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return None


def onedrive_en_ejecucion():
    """True si hay algún proceso OneDrive.exe corriendo (tasklist no requiere admin)."""
    try:
        salida = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq OneDrive.exe", "/NH"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        return "onedrive.exe" in salida.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def esperar_archivo_libre(ruta_archivo, timeout=None):
    """Espera a que ningún programa tenga bloqueado el archivo (si está bloqueado, OneDrive no lo sube)."""
    timeout = timeout or config.ONEDRIVE_TIMEOUT
    limite = time.time() + timeout
    intento = 0

    while time.time() < limite:
        intento += 1
        try:
            with open(ruta_archivo, "r+b"):
                return True
        except PermissionError:
            _log(f"Intento {intento}: el archivo sigue en uso (¿abierto en Excel?), esperando...")
            time.sleep(2)
        except FileNotFoundError:
            _log(f"No existe el archivo {ruta_archivo}")
            return False

    _log("El archivo siguió bloqueado; OneDrive no podrá subirlo hasta que se libere")
    return False


def cerrar_onedrive(exe, timeout=None):
    """Cierra OneDrive de forma limpia (/shutdown) y espera a que el proceso termine."""
    timeout = timeout or config.ONEDRIVE_TIMEOUT
    _log("Cerrando OneDrive...")
    subprocess.run([str(exe), "/shutdown"], timeout=timeout)

    limite = time.time() + timeout
    while time.time() < limite:
        if not onedrive_en_ejecucion():
            _log("OneDrive cerrado")
            return True
        time.sleep(1)

    _log("OneDrive no terminó de cerrarse a tiempo, se intenta iniciarlo de todas formas")
    return False


def iniciar_onedrive(exe):
    """Inicia OneDrive en segundo plano, desligado de este script (sigue vivo cuando Python termina)."""
    banderas = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(exe), "/background"],
        creationflags=banderas,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    limite = time.time() + config.ONEDRIVE_TIMEOUT
    while time.time() < limite:
        if onedrive_en_ejecucion():
            _log("OneDrive iniciado, sincronizando cambios pendientes")
            return True
        time.sleep(1)

    _log("No se confirmó que OneDrive haya arrancado; ábrelo a mano desde el menú Inicio")
    return False


def forzar_sincronizacion(ruta_archivo=None):
    """
    Reinicia OneDrive para que suba los cambios recién guardados.
    Nunca lanza error: si algo falla lo informa y el flujo principal sigue.
    """
    if not config.ONEDRIVE_FORZAR_SINCRONIZACION:
        return False

    if os.name != "nt":
        _log("Solo aplica en Windows, se omite")
        return False

    try:
        exe = ubicar_onedrive()
        if exe is None:
            _log("No se encontró OneDrive.exe; pon la ruta en config.ONEDRIVE_EXE")
            return False

        if ruta_archivo:
            esperar_archivo_libre(ruta_archivo)

        time.sleep(config.ONEDRIVE_ESPERA_ANTES)  # margen para que Windows termine de soltar el archivo

        cerrar_onedrive(exe)
        time.sleep(2)
        iniciado = iniciar_onedrive(exe)

        if iniciado:
            _log("Listo: revisa el ícono de OneDrive, debe mostrar las flechas de sincronización")
        return iniciado

    except Exception as e:
        _log(f"No se pudo forzar la sincronización ({type(e).__name__}: {e}); el archivo quedó guardado localmente")
        return False


if __name__ == "__main__":
    # Prueba rápida desde la raíz del proyecto:  python -m src.onedrive
    forzar_sincronizacion(config.EXCEL_ALERTAS)
