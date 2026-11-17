"""Verificación por reglas de la información mínima (paso 1 del proceso).

El enunciado nombra tres elementos: qué pasó, cuándo y qué necesita el usuario. Cada
uno se reconoce por marcadores del español; la empresa puede añadir los suyos y elegir
cuáles exige (supuesto: por defecto, los tres del enunciado). Es el respaldo del LLM.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum

from domain.texto import normalizar, patron_de_frases


class ElementoMinimo(StrEnum):
    """Los tres elementos del paso 1."""

    QUE_PASO = "que_paso"
    CUANDO = "cuando"
    QUE_NECESITA = "que_necesita"


_RAIZ_QUE_PASO = (
    r"fall\w*|averi\w*|dan(?:o|os|ado|ada|ados|adas)|rot[oa]s?|dejo de \w+|"
    r"no (?:funciona|sirve|prende|enciende|tengo|hay|llega|llego|ha llegado|me llego|"
    r"hace contacto|carga|abre)|error\w*|problema\w*|cobr\w*|presenta\w*|perd\w*|"
    r"robo|robaron|corte|cortes|cortaron|cortado|cortada|fuga\w*|huele|olor\w*|"
    r"retras\w*|demor\w*|accidente\w*|quem\w*|defect\w*|incumpl\w*|bloque\w*|"
    r"suspend\w*|extravi\w*|equivoc\w*|mal estado|sin servicio|se cayo|se dano"
)
_RAIZ_CUANDO = (
    r"hace (?:\d+|un|una|unos|unas|dos|tres|cuatro|cinco|varios|varias|mucho|poco)\b|"
    r"ayer|anoche|antier|anteayer|hoy|esta (?:manana|tarde|noche|semana)|desde\b|"
    r"el (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)|"
    r"(?:la|el) (?:semana|mes|ano) pasad[oa]|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|"
    r"diciembre|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}(?::\d{2})? ?(?:am|pm)|(?:dias|semanas|meses) (?:atras|seguid[oa]s)"
)
_RAIZ_QUE_NECESITA = (
    r"solicit\w*|necesit\w*|requier\w*|requer\w*|quiero|quisiera|pido|pedir|dese[oa]\w*|"
    r"por favor|ayud\w*|revis\w*|arregl\w*|repar\w*|cambi\w*|cancel\w*|reembols\w*|"
    r"devol\w*|devuelv\w*|informa\w*|saber|consult\w*|como puedo|me pueden|podrian|"
    r"agend\w*|program\w*|visita\w*|actualiz\w*|reclam\w*|reponer|reposicion"
)

_MARCADORES_BASE: dict[ElementoMinimo, re.Pattern[str]] = {
    ElementoMinimo.QUE_PASO: re.compile(rf"(?<!\w)(?:{_RAIZ_QUE_PASO})(?!\w)"),
    ElementoMinimo.CUANDO: re.compile(rf"(?<!\w)(?:{_RAIZ_CUANDO})(?!\w)"),
    ElementoMinimo.QUE_NECESITA: re.compile(rf"(?<!\w)(?:{_RAIZ_QUE_NECESITA})(?!\w)"),
}

REQUERIDOS_POR_DEFECTO: frozenset[ElementoMinimo] = frozenset(ElementoMinimo)

_MIN_PALABRAS = 5
"""Debajo de esto no hay solicitud que gestionar, aunque aparezca un marcador suelto."""


@dataclass(frozen=True)
class EvaluacionInformacion:
    """Qué elementos se encontraron y si alcanzan para gestionar el caso."""

    encontrados: frozenset[ElementoMinimo]
    faltantes: frozenset[ElementoMinimo]

    @property
    def suficiente(self) -> bool:
        return not self.faltantes


def evaluar_informacion_minima(
    texto: str,
    requeridos: Collection[ElementoMinimo] = REQUERIDOS_POR_DEFECTO,
    marcadores_extra: Mapping[ElementoMinimo, Collection[str]] | None = None,
) -> EvaluacionInformacion:
    """Busca cada elemento en el texto y compara con los que la empresa exige.

    marcadores_extra son frases propias de la empresa (por ejemplo, "sin señal" para
    una de telecomunicaciones) que cuentan como el elemento indicado.
    """
    normalizado = normalizar(texto)
    extra = marcadores_extra or {}
    encontrados: set[ElementoMinimo] = set()
    for elemento, patron in _MARCADORES_BASE.items():
        patron_extra = patron_de_frases(tuple(extra.get(elemento, ())))
        if patron.search(normalizado) or (patron_extra and patron_extra.search(normalizado)):
            encontrados.add(elemento)
    # Una pregunta explícita ya dice qué necesita el usuario.
    if "?" in texto:
        encontrados.add(ElementoMinimo.QUE_NECESITA)
    exigidos = frozenset(requeridos)
    if len(normalizado.split()) < _MIN_PALABRAS:
        # Texto demasiado corto: se cierra aunque un marcador suelto haya coincidido.
        return EvaluacionInformacion(frozenset(), exigidos or frozenset(ElementoMinimo))
    return EvaluacionInformacion(frozenset(encontrados), exigidos - encontrados)


_SEPARADOR_ORACIONES = re.compile(r"(?<=[.!?\n])\s+|\s+\.(?=\s|$)")
_CONECTOR_CAUSA = re.compile(r"\b(?:porque|ya que|debido a que|pues)\b", re.IGNORECASE)
_NUMERO_LARGO = re.compile(r"\d[\d.\-]{4,}\d")
_MAX_CARACTERES_HECHO = 160


def extraer_hecho_principal(texto: str) -> str | None:
    """Fragmento del texto que cuenta qué pasó, para citarlo en la justificación.

    Toma la primera oración con un marcador de "qué pasó"; si trae un conector de causa
    ("porque"), se queda con lo que sigue. Los números largos (documentos) se ocultan.
    """
    patron = _MARCADORES_BASE[ElementoMinimo.QUE_PASO]
    for oracion in _SEPARADOR_ORACIONES.split(texto):
        if not patron.search(normalizar(oracion)):
            continue
        partes = _CONECTOR_CAUSA.split(oracion, maxsplit=1)
        hecho = partes[-1] if len(partes) > 1 and patron.search(normalizar(partes[-1])) else oracion
        hecho = _NUMERO_LARGO.sub("[documento]", hecho).strip(" .,;:")
        if len(hecho) > _MAX_CARACTERES_HECHO:
            hecho = hecho[:_MAX_CARACTERES_HECHO].rsplit(" ", 1)[0] + "..."
        return hecho or None
    return None
