"""Próximo paso y estado del caso (pasos 1, 5, 6 y 7 del proceso).

Las delegaciones las fija el contrato de cada empresa: qué categorías resuelve el BPO
(RESPUESTA_DIRECTA) y cuáles pasan a la empresa (GESTION_EXTERNA).
"""

from __future__ import annotations

from collections.abc import Mapping

from domain.contrato import EstadoCaso, ProximoPaso

PASOS_DELEGABLES = frozenset({ProximoPaso.GESTION_EXTERNA, ProximoPaso.RESPUESTA_DIRECTA})


def decidir_proximo_paso(
    informacion_suficiente: bool,
    categoria: str | None,
    delegaciones: Mapping[str, ProximoPaso],
) -> ProximoPaso:
    """Cierra si falta información; si no, sigue la delegación de la categoría.

    Una categoría sin delegación va a GESTION_EXTERNA: ante la duda, el caso lo ve la
    empresa en vez de responderse sin autorización (supuesto). La carga de la
    configuración exige una delegación por categoría, así que esto es solo una red.
    """
    if not informacion_suficiente:
        return ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE
    if categoria is None:
        return ProximoPaso.GESTION_EXTERNA
    return delegaciones.get(categoria, ProximoPaso.GESTION_EXTERNA)


def estado_para(paso: ProximoPaso) -> EstadoCaso:
    """La gestión externa queda pendiente (paso 6); lo demás lo cierra el BPO (pasos 1 y 7)."""
    if paso is ProximoPaso.GESTION_EXTERNA:
        return EstadoCaso.PENDIENTE
    return EstadoCaso.CERRADO
