"""Extracción por reglas del documento del cliente.

Es el respaldo cuando el LLM no responde y la verificación de lo que el LLM dice. El
enunciado solo muestra la cédula ("numero de cédula es 102045678" -> CC); los demás
tipos colombianos (CE, NIT, TI, PA) son supuesto y se documentan.
"""

from __future__ import annotations

import re

from domain.contrato import DocumentoCliente
from domain.texto import normalizar

# Orden importa: "cedula de extranjeria" debe ganar antes que "cedula" sola.
_ETIQUETAS: tuple[tuple[str, str], ...] = (
    ("CE", r"cedula de extranjeria|\bc\.\s?e\b\.?|\bce\b"),
    ("CC", r"cedula de ciudadania|cedula|\bc\.\s?c\b\.?|\bcc\b"),
    ("NIT", r"\bnit\b"),
    ("TI", r"tarjeta de identidad|\bt\.\s?i\b\.?"),
    ("PA", r"pasaporte"),
)

# Entre la etiqueta y el número caben palabras de relleno ("mi numero de cédula es",
# "No.", ":"), pero sin cruzar a otra oración ni a otro número.
_RELLENO = r"[^\d!?\n]{0,30}?"

# Número con puntos o guion de miles ("102.045.678", "900123456-7"); pasaporte alfanumérico.
_NUMERO = r"(\d[\d.\-]{3,16}\d)"
_NUMERO_PASAPORTE = r"([a-z]{0,3}\d[a-z\d]{4,11})\b"

_MIN_DIGITOS = 5
_MAX_DIGITOS = 12

_PATRONES = tuple(
    (
        tipo,
        re.compile(rf"(?:{etiqueta}){_RELLENO}{_NUMERO_PASAPORTE if tipo == 'PA' else _NUMERO}"),
    )
    for tipo, etiqueta in _ETIQUETAS
)


def _limpiar_numero(tipo: str, crudo: str) -> str | None:
    """Deja solo dígitos (el NIT conserva el guion del dígito de verificación)."""
    if tipo == "PA":
        return crudo.upper()
    if tipo == "NIT" and "-" in crudo:
        base, _, verificacion = crudo.rpartition("-")
        digitos = re.sub(r"\D", "", base)
        if not (_MIN_DIGITOS <= len(digitos) <= _MAX_DIGITOS) or not verificacion.isdigit():
            return None
        return f"{digitos}-{verificacion}"
    digitos = re.sub(r"\D", "", crudo)
    if not (_MIN_DIGITOS <= len(digitos) <= _MAX_DIGITOS):
        return None
    return digitos


def extraer_documento(texto: str) -> DocumentoCliente | None:
    """Devuelve el primer documento que aparece en el texto, o None si no hay ninguno.

    Si hay dos etiquetas, gana la que aparece primero en el texto: es la que el cliente
    usó para presentarse.
    """
    normalizado = normalizar(texto)
    candidatos: list[tuple[int, DocumentoCliente]] = []
    for tipo, patron in _PATRONES:
        for coincidencia in patron.finditer(normalizado):
            numero = _limpiar_numero(tipo, coincidencia.group(1))
            if numero:
                candidatos.append((coincidencia.start(), DocumentoCliente(tipo, numero)))
                break
    if not candidatos:
        return None
    return min(candidatos, key=lambda par: par[0])[1]
