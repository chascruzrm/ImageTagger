"""Configuración compartida de la aplicación: rutas, config.ini, log y fuente."""

import configparser
import logging
import os
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from tkinter import font as tkfont

# Carpeta de la aplicación (donde están main.py y config.ini).
DIRECTORIO_APP = os.path.dirname(os.path.abspath(__file__))
# Configuración: [GENERAL] directorio_monitoreo = <ruta>
#                [GENERAL] directorio_database = <ruta> (opcional)
ARCHIVO_CONFIG = os.path.join(DIRECTORIO_APP, "config.ini")


def _leer_config():
    """Lee config.ini. Lanza ValueError si no existe y configparser.Error si
    tiene un formato inválido."""
    config = configparser.ConfigParser(interpolation=None)
    # utf-8-sig: acepta el archivo con o sin BOM (el Bloc de notas puede agregarlo).
    if not config.read(ARCHIVO_CONFIG, encoding="utf-8-sig"):
        raise ValueError(f"No se encontró el archivo de configuración {ARCHIVO_CONFIG}. "
                         "Cree uno a partir de config.example.ini.")
    return config


# Carpeta de la base de datos si config.ini no indica otra (o no se puede crear).
DIRECTORIO_DATABASE_DEFAULT = os.path.join(DIRECTORIO_APP, "database")


def _leer_directorio_database():
    """[GENERAL] directorio_database de config.ini. Una ruta relativa se toma
    desde DIRECTORIO_APP. Si falta la clave, o config.ini no existe o es
    inválido (ese error lo informa leer_directorio_monitoreo() al iniciar), se
    usa DIRECTORIO_DATABASE_DEFAULT."""
    try:
        directorio = _leer_config().get("GENERAL", "directorio_database", fallback="").strip()
    except (ValueError, configparser.Error):
        directorio = ""
    if not directorio:
        return DIRECTORIO_DATABASE_DEFAULT
    # Si `directorio` es absoluto, join lo devuelve sin cambios.
    return os.path.normpath(os.path.join(DIRECTORIO_APP, directorio))


def _preparar_directorio_database():
    """Devuelve (directorio, aviso): la carpeta de la base de datos, creada si no
    existía, y un mensaje para el usuario (None si no hubo problemas).

    Si no se puede crear la carpeta configurada, se usa DIRECTORIO_DATABASE_DEFAULT
    y el aviso lo explica. Si tampoco se puede crear la de por defecto, no se avisa
    acá: lo detecta verificar_escritura() al iniciar.
    """
    directorio = _leer_directorio_database()
    try:
        os.makedirs(directorio, exist_ok=True)
        return directorio, None
    except OSError as e:
        if directorio == DIRECTORIO_DATABASE_DEFAULT:
            return directorio, None
        aviso = (f"No se pudo crear la carpeta de la base de datos:\n\n{directorio}\n\n{e}\n\n"
                 f"Se usará la carpeta por defecto:\n\n{DIRECTORIO_DATABASE_DEFAULT}")
    try:
        os.makedirs(DIRECTORIO_DATABASE_DEFAULT, exist_ok=True)
    except OSError:
        pass
    return DIRECTORIO_DATABASE_DEFAULT, aviso


def verificar_escritura(directorio):
    """Lanza OSError si no se puede crear un archivo en `directorio`."""
    # Se crea y borra un archivo de prueba: os.access no es confiable en Windows.
    with tempfile.TemporaryFile(dir=directorio):
        pass


# Carpeta donde se guardan las imágenes procesadas con su JSON. Se resuelve (y se
# crea) al importar este módulo porque los demás la importan como constante;
# main() muestra AVISO_DATABASE, si lo hay, y verifica que se pueda escribir.
DIRECTORIO_DATABASE, AVISO_DATABASE = _preparar_directorio_database()
# Carpeta donde van las imágenes borradas (con su JSON, si lo tienen).
DIRECTORIO_PAPELERA = os.path.join(DIRECTORIO_APP, "Borrados")
# Log de la aplicación (errores e información de inicio). Rota al llegar a
# 1 MB y conserva los 3 anteriores (imagetagger.log.1, .2, .3).
DIRECTORIO_LOGS = os.path.join(DIRECTORIO_APP, "logs")
ARCHIVO_LOG = os.path.join(DIRECTORIO_LOGS, "imagetagger.log")
TAMANIO_MAX_LOG = 1024 * 1024
CANTIDAD_LOGS_ANTERIORES = 3

FUENTE = ("Arial", 12)

# Evento virtual que el editor genera sobre la galería (ventana principal) al
# guardar o borrar una imagen: la galería relee la lista.
EVENTO_DATABASE_MODIFICADA = "<<DatabaseModificada>>"


def leer_directorio_monitoreo():
    """Lee [GENERAL] directorio_monitoreo de config.ini.

    Lanza ValueError si falta el archivo o la clave, y configparser.Error si el
    archivo tiene un formato inválido.
    """
    directorio = _leer_config().get("GENERAL", "directorio_monitoreo", fallback="").strip()
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
