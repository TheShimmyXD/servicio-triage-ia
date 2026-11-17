"""Tipos de documento del cliente y su extracción por reglas.

Es el respaldo cuando el LLM no responde y la verificación de lo que el LLM dice. El
enunciado solo muestra la cédula ("numero de cédula es 102045678" -> CC); los demás
tipos colombianos (CE, NIT, TI, PA) son supuesto y se documentan. Los tipos vienen de
configuración (configuracion/tipos_documento.yaml): sumar uno no toca el código.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from domain.contrato import DocumentoCliente
from domain.texto import normalizar


class FormatoNumero(StrEnum):
    NUMERICO = "numerico"
    ALFANUMERICO = "alfanumerico"
    """Pasaporte: letras y dígitos, en mayúsculas."""
    CON_DIGITO_VERIFICACION = "con_digito_verificacion"
    """NIT: dígitos y, si lo trae, el guion con el dígito de verificación."""


@dataclass(frozen=True)
class TipoDocumento:
    codigo: str
    nombre: str
    """Cómo se le explica al LLM ("cédula de ciudadanía")."""
    etiqueta: str
    """Expresión regular sobre el texto en minúsculas y sin tildes."""
    formato: FormatoNumero = FormatoNumero.NUMERICO


# Entre la etiqueta y el número caben palabras de relleno ("mi numero de cédula es",
# "No.", ":"), pero sin cruzar a otra oración ni a otro número.
_RELLENO = r"[^\d!?\n]{0,30}?"

# Número con puntos o guion de miles ("102.045.678", "900123456-7"); pasaporte alfanumérico.
_NUMERO = r"(\d[\d.\-]{3,16}\d)"
_NUMERO_ALFANUMERICO = r"([a-z]{0,3}\d[a-z\d]{4,11})\b"

_MIN_DIGITOS = 5
_MAX_DIGITOS = 12


@dataclass(frozen=True)
class TiposDocumento:
    """Los tipos que el servicio reconoce, en orden de precedencia.

    El orden importa: "cedula de extranjeria" debe ir antes que "cedula" sola, porque
    ante dos etiquetas en la misma posición gana la primera de la lista.
    """

    tipos: tuple[TipoDocumento, ...]
    _patrones: tuple[tuple[TipoDocumento, re.Pattern[str]], ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        patrones = tuple(
            (
                tipo,
                re.compile(
                    rf"(?:{tipo.etiqueta}){_RELLENO}"
                    + (
                        _NUMERO_ALFANUMERICO
                        if tipo.formato is FormatoNumero.ALFANUMERICO
                        else _NUMERO
                    )
                ),
            )
            for tipo in self.tipos
        )
        object.__setattr__(self, "_patrones", patrones)

    @classmethod
    def de(cls, tipos: Iterable[TipoDocumento]) -> TiposDocumento:
        return cls(tuple(tipos))

    @property
    def codigos(self) -> frozenset[str]:
        return frozenset(t.codigo for t in self.tipos)

    def extraer(self, texto: str) -> DocumentoCliente | None:
        """Devuelve el primer documento que aparece en el texto, o None si no hay ninguno.

        Si hay dos etiquetas, gana la que aparece primero en el texto: es la que el
        cliente usó para presentarse.
        """
        normalizado = normalizar(texto)
        candidatos: list[tuple[int, DocumentoCliente]] = []
        for tipo, patron in self._patrones:
            for coincidencia in patron.finditer(normalizado):
                numero = _limpiar_numero(tipo.formato, coincidencia.group(1))
                if numero:
                    candidatos.append((coincidencia.start(), DocumentoCliente(tipo.codigo, numero)))
                    break
        if not candidatos:
            return None
        return min(candidatos, key=lambda par: par[0])[1]


def _limpiar_numero(formato: FormatoNumero, crudo: str) -> str | None:
    """Deja solo dígitos (el NIT conserva el guion del dígito de verificación)."""
    if formato is FormatoNumero.ALFANUMERICO:
        return crudo.upper()
    if formato is FormatoNumero.CON_DIGITO_VERIFICACION and "-" in crudo:
        base, _, verificacion = crudo.rpartition("-")
        digitos = re.sub(r"\D", "", base)
        if not (_MIN_DIGITOS <= len(digitos) <= _MAX_DIGITOS) or not verificacion.isdigit():
            return None
        return f"{digitos}-{verificacion}"
    digitos = re.sub(r"\D", "", crudo)
    if not (_MIN_DIGITOS <= len(digitos) <= _MAX_DIGITOS):
        return None
    return digitos


def extraer_documento(texto: str, tipos: TiposDocumento) -> DocumentoCliente | None:
    return tipos.extraer(texto)
