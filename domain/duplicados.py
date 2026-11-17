"""Qué hacer cuando llega una solicitud que ya se atendió (clave: compania y solicitud_id).

El BPO puede reenviar la misma solicitud por un timeout o un doble clic; crear dos casos
en la plataforma del cliente duplicaría el trabajo de la empresa. La decisión es pura y
el repositorio solo guarda lo ya atendido.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.contrato import EstadoCaso, ResultadoTriage


class AccionAnteDuplicado(StrEnum):
    NUEVA = "nueva"
    """No hay registro con esa clave: se hace el triage."""
    DEVOLVER_EXISTENTE = "devolver_existente"
    """Mismo texto ya atendido: se devuelve el resultado guardado sin crear otro caso."""
    REINTENTAR = "reintentar"
    """Mismo texto, pero la plataforma falló la vez anterior: se vuelve a intentar."""
    CONFLICTO = "conflicto"
    """Mismo id con otro texto: el cliente reutilizó el id; se rechaza explícitamente."""


@dataclass(frozen=True)
class SolicitudAtendida:
    """Lo que guarda el repositorio por cada clave."""

    texto_normalizado: str
    resultado: ResultadoTriage


class SolicitudEnConflicto(ValueError):
    """El id ya existe para la empresa con otra descripción."""

    codigo = "SOLICITUD_DUPLICADA"

    def __init__(self, compania: str, solicitud_id: str) -> None:
        self.compania = compania
        self.solicitud_id = solicitud_id
        super().__init__(
            f'La solicitud "{solicitud_id}" de {compania} ya fue atendida con otra '
            "descripción. Use un solicitud_id nuevo."
        )


def normalizar_texto(texto: str) -> str:
    """Ignora espacios de más: el mismo mensaje copiado dos veces no es un conflicto."""
    return " ".join(texto.split())


def decidir_ante_duplicado(previa: SolicitudAtendida | None, texto: str) -> AccionAnteDuplicado:
    if previa is None:
        return AccionAnteDuplicado.NUEVA
    if previa.texto_normalizado != normalizar_texto(texto):
        return AccionAnteDuplicado.CONFLICTO
    if previa.resultado.estado is EstadoCaso.ERROR_PLATAFORMA:
        return AccionAnteDuplicado.REINTENTAR
    return AccionAnteDuplicado.DEVOLVER_EXISTENTE
