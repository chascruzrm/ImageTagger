"""Utilidades de texto compartidas."""

import unicodedata


def normalizar(texto):
    """Minúsculas y sin acentos, para buscar sin distinguir 'Pérez' de 'PEREZ'."""
    sin_acentos = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").casefold()
