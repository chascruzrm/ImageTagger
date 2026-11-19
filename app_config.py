"""Configuración compartida de la aplicación: rutas, config.ini y fuente."""

import configparser
import os
from tkinter import font as tkfont

# Carpeta de la aplicación (donde están main.py y config.ini).
DIRECTORIO_APP = os.path.dirname(os.path.abspath(__file__))
# Configuración: [GENERAL] directorio_monitoreo = <ruta>
ARCHIVO_CONFIG = os.path.join(DIRECTORIO_APP, "config.ini")
# Carpeta donde se guardan las imágenes procesadas con su JSON.
DIRECTORIO_DATABASE = os.path.join(DIRECTORIO_APP, "database")
# Carpeta donde van las imágenes descartadas (con su JSON, si lo tienen).
DIRECTORIO_DESCARTADOS = os.path.join(DIRECTORIO_APP, "descartados")

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


def configurar_fuentes():
    """Arial 12 como fuente por defecto de todos los widgets (requiere un Tk creado).

    Incluye TkFixedFont, que es la que usan por defecto los cuadros de texto
    multilínea (Notas).
    """
    for nombre in tkfont.names():
        if nombre.startswith("Tk"):
            tkfont.nametofont(nombre).configure(family=FUENTE[0], size=FUENTE[1])
