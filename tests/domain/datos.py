"""Datos compartidos por las pruebas del dominio."""

from __future__ import annotations

from domain.contrato import Prioridad, ProximoPaso
from domain.prioridad import ReglasPrioridad, SenalPrioridad

# Ejemplo de INPUT del enunciado, tal cual (con sus errores de tipeo).
TEXTO_JUANA = (
    "Mi nombre es Juana y mi numero de cédula es 102045678 . Solicito una revision urgente "
    "porque la estufa qué compre hace 2 semanas con la empresa presenta fallas (no está "
    "haciendo contacto con la llave del gas) "
)

# Pide algo, pero no dice qué pasó ni cuándo.
TEXTO_INCOMPLETO = "Buenas tardes, quiero que me ayuden con lo de siempre por favor"

REGLAS_GAS = ReglasPrioridad(
    por_defecto=Prioridad.BAJA,
    por_categoria={"Incidente técnico": Prioridad.MEDIA, "Consulta": Prioridad.BAJA},
    senales=(
        SenalPrioridad(Prioridad.ALTA, ("urgente", "fuga de gas", "riesgo")),
        SenalPrioridad(Prioridad.MEDIA, ("reclamo",)),
    ),
)

DELEGACIONES_GAS = {
    "Incidente técnico": ProximoPaso.GESTION_EXTERNA,
    "Consulta": ProximoPaso.RESPUESTA_DIRECTA,
}
