"""Prioridad por reglas de la empresa (paso 3 del proceso).

Cada empresa fija una prioridad base por categoría y señales del texto ("urgente",
"riesgo", "fuga") que la suben. Gana la mayor; el motivo queda para la justificación.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from domain.contrato import Prioridad
from domain.texto import normalizar, patron_de_frases

# Una señal escrita "huele a gas" debe reconocer "huele muchísimo a gas": la gente
# intercala adverbios. Más de dos palabras en medio ya junta frases sin relación.
_HOLGURA_SENALES = 2

FUENTE_REGLAS = "reglas de la empresa"


@dataclass(frozen=True)
class SenalPrioridad:
    """Frases que, si aparecen en la solicitud, piden al menos esta prioridad."""

    prioridad: Prioridad
    frases: tuple[str, ...]


@dataclass(frozen=True)
class ReglasPrioridad:
    """Reglas de una empresa. Vienen de su YAML; aquí no se nombra ninguna empresa."""

    por_defecto: Prioridad
    por_categoria: Mapping[str, Prioridad] = field(default_factory=dict)
    senales: Sequence[SenalPrioridad] = ()


@dataclass(frozen=True)
class DecisionPrioridad:
    """Prioridad elegida, por qué y de dónde salió (reglas o servicio externo)."""

    prioridad: Prioridad
    motivo: str
    fuente: str = FUENTE_REGLAS


def calcular_prioridad(
    categoria: str | None, texto: str, reglas: ReglasPrioridad
) -> DecisionPrioridad:
    """Aplica la base de la categoría y sube con la señal más fuerte que aparezca."""
    if categoria is not None and categoria in reglas.por_categoria:
        prioridad = reglas.por_categoria[categoria]
        motivo = f'la categoría "{categoria}" tiene prioridad base {prioridad.value}'
    else:
        prioridad = reglas.por_defecto
        motivo = f"prioridad por defecto de la empresa ({prioridad.value})"

    normalizado = normalizar(texto)
    for senal in sorted(reglas.senales, key=lambda s: s.prioridad.peso, reverse=True):
        if senal.prioridad.peso <= prioridad.peso:
            break
        patron = patron_de_frases(senal.frases, _HOLGURA_SENALES)
        coincidencia = patron.search(normalizado) if patron else None
        if coincidencia:
            prioridad = senal.prioridad
            motivo = f'la solicitud menciona "{coincidencia.group(0)}"'
            break
    return DecisionPrioridad(prioridad, motivo)
