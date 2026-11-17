"""Normalización de texto libre para comparar sin depender de tildes ni mayúsculas."""

from __future__ import annotations

import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")


def quitar_tildes(texto: str) -> str:
    """Quita tildes y diéresis; la ñ pasa a n (las reglas no dependen de ella)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio entre palabras.

    Las solicitudes llegan escritas a mano ("cédula", "cedula", "CÉDULA"); las reglas
    se escriben una sola vez en esta forma.
    """
    return _ESPACIOS.sub(" ", quitar_tildes(texto).lower()).strip()


def normalizar_nombre(nombre: str) -> str:
    """Forma canónica de un nombre de empresa: mayúsculas, sin tildes ni espacios dobles."""
    return _ESPACIOS.sub(" ", quitar_tildes(nombre).upper()).strip()


def patron_de_frases(frases: tuple[str, ...] | list[str]) -> re.Pattern[str] | None:
    """Compila frases en un patrón que solo acepta palabras completas.

    Las frases se normalizan antes, así una regla escrita "fuga de gás" encuentra
    "FUGA DE GAS". Devuelve None si no hay frases.
    """
    limpias = sorted({normalizar(f) for f in frases if f.strip()}, key=len, reverse=True)
    if not limpias:
        return None
    alternativas = "|".join(re.escape(f) for f in limpias)
    return re.compile(rf"(?<!\w)(?:{alternativas})(?!\w)")
