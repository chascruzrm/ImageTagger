"""Modelos de datos."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CARACTERES = 25
MAX_BYTES_NOTAS = 1024 * 1024  # 1 MB, medido en UTF-8


class Persona(BaseModel):
    """Datos de la persona que aparece en una imagen."""

    # Quita los espacios periféricos de todos los textos.
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo_objeto: Literal["persona"] = "persona"
    apellido: str = Field(default="", max_length=MAX_CARACTERES)
    nombre: str = Field(min_length=1, max_length=MAX_CARACTERES)
    documento: str = Field(default="", max_length=MAX_CARACTERES)
    notas: str = ""

    @field_validator("apellido", "nombre")
    @classmethod
    def _a_mayusculas(cls, valor: str) -> str:
        # Recortar: algunas letras se expanden al pasar a mayúsculas ("ß" -> "SS").
        return valor.upper()[:MAX_CARACTERES]

    @field_validator("notas")
    @classmethod
    def _limitar_notas(cls, valor: str) -> str:
        if len(valor.encode("utf-8")) > MAX_BYTES_NOTAS:
            raise ValueError(f"las notas superan el máximo de {MAX_BYTES_NOTAS} bytes")
        return valor
