"""Clasificación de respaldo por palabras clave de cada categoría.

Se usa cuando el LLM no responde o responde algo que no valida. Gana la categoría con
más palabras clave distintas en el texto; en empate, la que aparece antes en la
configuración de la empresa (el orden del YAML es la preferencia del negocio).
"""

from __future__ import annotations

from collections.abc import Sequence

from domain.empresa import Categoria
from domain.texto import normalizar, patron_de_frases


def clasificar_por_palabras_clave(texto: str, categorias: Sequence[Categoria]) -> str | None:
    """Devuelve el nombre de la categoría con más coincidencias, o None si ninguna coincide."""
    normalizado = normalizar(texto)
    mejor: str | None = None
    mejor_puntaje = 0
    for categoria in categorias:
        patron = patron_de_frases(categoria.palabras_clave)
        if patron is None:
            continue
        puntaje = len(set(patron.findall(normalizado)))
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = categoria.nombre, puntaje
    return mejor
