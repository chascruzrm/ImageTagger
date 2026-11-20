"""Fuentes de valores para el autocompletado de los campos de Persona.

Se ejecutan en un thread aparte (ver autocompletado.Autocompletado): no deben
usar tkinter. Por ahora leen todos los JSON de database en cada búsqueda; si la
base crece habrá que optimizar _buscar_valores (por ejemplo, con un índice en
memoria), sin cambiar la firma de las funciones get_autocompletion_*.
"""

import json
import logging
import os
import threading

from app_config import DIRECTORIO_DATABASE
from textos import normalizar

log = logging.getLogger(__name__)


def _buscar_valores(campo: str, texto: str, cancelado: threading.Event) -> list[str]:
    """Valores distintos de `campo` en los JSON de DIRECTORIO_DATABASE que empiezan
    con `texto`, sin distinguir mayúsculas ni acentos, ordenados alfabéticamente.

    Si `cancelado` se activa durante la búsqueda, devuelve [] sin terminar.
    """
    buscado = normalizar(texto)
    try:
        nombres = os.listdir(DIRECTORIO_DATABASE)
    except OSError:
        return []
    valores = set()
    for nombre in nombres:
        if cancelado.is_set():
            return []
        if not nombre.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(DIRECTORIO_DATABASE, nombre), encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, UnicodeDecodeError, ValueError):
            continue  # archivo ilegible o JSON inválido: se ignora
        valor = datos.get(campo) if isinstance(datos, dict) else None
        if isinstance(valor, str):
            valor = valor.strip()
            if valor and normalizar(valor).startswith(buscado):
                valores.add(valor)
    return sorted(valores, key=lambda v: (normalizar(v), v))


def get_autocompletion_apellido(texto: str, cancelado: threading.Event) -> list[str]:
    return _buscar_valores("apellido", texto, cancelado)


def get_autocompletion_nombre(texto: str, cancelado: threading.Event) -> list[str]:
    return _buscar_valores("nombre", texto, cancelado)


def get_autocompletion_documento(texto: str, cancelado: threading.Event) -> list[str]:
    return _buscar_valores("documento", texto, cancelado)
