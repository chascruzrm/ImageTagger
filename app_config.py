"""Configuración compartida de la aplicación: rutas, config.ini, log y fuente."""

import configparser
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from tkinter import font as tkfont

# Carpeta de la aplicación (donde están main.py y config.ini).
DIRECTORIO_APP = os.path.dirname(os.path.abspath(__file__))
# Configuración: [GENERAL] directorio_monitoreo = <ruta>
ARCHIVO_CONFIG = os.path.join(DIRECTORIO_APP, "config.ini")
# Carpeta donde se guardan las imágenes procesadas con su JSON.
DIRECTORIO_DATABASE = os.path.join(DIRECTORIO_APP, "database")
# Carpeta donde van las imágenes descartadas (con su JSON, si lo tienen).
DIRECTORIO_DESCARTADOS = os.path.join(DIRECTORIO_APP, "descartados")
# Log de la aplicación (errores e información de inicio). Rota al llegar a
# 1 MB y conserva los 3 anteriores (imagetagger.log.1, .2, .3).
DIRECTORIO_LOGS = os.path.join(DIRECTORIO_APP, "logs")
ARCHIVO_LOG = os.path.join(DIRECTORIO_LOGS, "imagetagger.log")
TAMANIO_MAX_LOG = 1024 * 1024
CANTIDAD_LOGS_ANTERIORES = 3

FUENTE = ("Arial", 12)

# Evento virtual que el editor genera sobre la galería (ventana principal) al
# guardar o descartar una imagen: la galería relee la lista.
EVENTO_DATABASE_MODIFICADA = "<<DatabaseModificada>>"


def leer_directorio_monitoreo():
    """Lee [GENERAL] directorio_monitoreo de config.ini.

    Lanza ValueError si falta el archivo o la clave, y configparser.Error si el
    archivo tiene un formato inválido.
    """
    config = configparser.ConfigParser(interpolation=None)
    # utf-8-sig: acepta el archivo con o sin BOM (el Bloc de notas puede agregarlo).
    if not config.read(ARCHIVO_CONFIG, encoding="utf-8-sig"):
        raise ValueError(f"No se encontró el archivo de configuración {ARCHIVO_CONFIG}. "
                         "Cree uno a partir de config.example.ini.")
    directorio = config.get("GENERAL", "directorio_monitoreo", fallback="").strip()
    if not directorio:
        raise ValueError(f"Falta 'directorio_monitoreo' en la sección [GENERAL] de {ARCHIVO_CONFIG}.")
    return directorio


def configurar_log():
    """Configura el log: archivo ARCHIVO_LOG y, si hay consola (python, no
    pythonw), también la salida de errores. Registra además los errores no
    controlados del programa y de los threads. Se puede llamar más de una vez.
    """
    raiz = logging.getLogger()
    if getattr(configurar_log, "_hecho", False):
        return
    configurar_log._hecho = True
    raiz.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s")

    try:
        os.makedirs(DIRECTORIO_LOGS, exist_ok=True)
        archivo = RotatingFileHandler(ARCHIVO_LOG, maxBytes=TAMANIO_MAX_LOG,
                                      backupCount=CANTIDAD_LOGS_ANTERIORES, encoding="utf-8")
        archivo.setFormatter(formato)
        raiz.addHandler(archivo)
    except OSError as e:
        if sys.stderr is not None:
            print(f"No se pudo abrir el log {ARCHIVO_LOG}: {e}", file=sys.stderr)

    if sys.stderr is not None:  # con pythonw no hay consola
        consola = logging.StreamHandler(sys.stderr)
        consola.setFormatter(formato)
        raiz.addHandler(consola)

    log = logging.getLogger("imagetagger")

    def error_no_controlado(tipo, valor, traza):
        if issubclass(tipo, KeyboardInterrupt):
            sys.__excepthook__(tipo, valor, traza)
            return
        log.critical("Error no controlado", exc_info=(tipo, valor, traza))
    sys.excepthook = error_no_controlado

    def error_en_thread(args):
        if args.exc_type is SystemExit:
            return
        log.error("Error no controlado en el thread %s", args.thread.name if args.thread else "?",
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = error_en_thread


def configurar_fuentes():
    """Arial 12 como fuente por defecto de todos los widgets (requiere un Tk creado).

    Incluye TkFixedFont, que es la que usan por defecto los cuadros de texto
    multilínea (Notas).
    """
    for nombre in tkfont.names():
        if nombre.startswith("Tk"):
            tkfont.nametofont(nombre).configure(family=FUENTE[0], size=FUENTE[1])
