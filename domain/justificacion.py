"""Justificación del triage (paso 4): breve y con datos de la solicitud."""

from __future__ import annotations

from domain.contrato import JUSTIFICACION_INFORMACION_INSUFICIENTE, ProximoPaso
from domain.prioridad import DecisionPrioridad

_TEXTO_PASO = {
    ProximoPaso.GESTION_EXTERNA: "requiere gestión de la empresa (delegación externa)",
    ProximoPaso.RESPUESTA_DIRECTA: "el BPO responde directamente (delegación del contrato)",
}


def construir_justificacion(
    paso: ProximoPaso,
    categoria: str | None,
    decision: DecisionPrioridad | None,
    hecho: str | None,
) -> str:
    """Arma la justificación con el hecho citado, la prioridad con su fuente y el paso.

    El cierre por información insuficiente usa el texto literal del paso 1.
    """
    if paso is ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE:
        return JUSTIFICACION_INFORMACION_INSUFICIENTE

    partes: list[str] = []
    encabezado = categoria or "Solicitud sin categoría"
    partes.append(f'{encabezado}: "{hecho}".' if hecho else f"{encabezado}.")
    if decision is not None:
        partes.append(
            f"Prioridad {decision.prioridad.value} porque {decision.motivo} "
            f"(fuente: {decision.fuente})."
        )
    paso_texto = _TEXTO_PASO[paso]
    partes.append(paso_texto[0].upper() + paso_texto[1:] + ".")
    return " ".join(partes)
