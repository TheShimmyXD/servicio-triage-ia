"""Contadores de eventos por empresa, consultables en GET /metricas.

Sirven para vigilar lo que el triage absorbe sin caerse (fallas de plataforma, LLM caído,
duplicados). En la nube los mismos eventos van a métricas del proveedor con alarmas;
aquí viven en memoria del proceso y se reinician con él.
"""

from __future__ import annotations

import threading
from collections import Counter
from enum import StrEnum


class Evento(StrEnum):
    CASO_CREADO = "casos_creados"
    INTENTO_FALLIDO = "intentos_fallidos_plataforma"
    CASO_NO_CREADO = "casos_no_creados"
    """Se agotaron los reintentos: el caso necesita atención."""
    DUPLICADO_DEVUELTO = "duplicados_devueltos"
    CONFLICTO = "conflictos_de_id"
    LLM_FALLIDO = "llm_fallidos"
    """El LLM falló o respondió fuera del esquema; atendieron las reglas."""


class Metricas:
    def __init__(self) -> None:
        self._conteos: dict[Evento, Counter[str]] = {evento: Counter() for evento in Evento}
        # Los endpoints síncronos corren en varios hilos.
        self._candado = threading.Lock()

    def sumar(self, evento: Evento, empresa: str) -> None:
        with self._candado:
            self._conteos[evento][empresa] += 1

    def contar(self, evento: Evento, empresa: str | None = None) -> int:
        with self._candado:
            conteo = self._conteos[evento]
            return conteo[empresa] if empresa else sum(conteo.values())

    def foto(self) -> dict[str, dict[str, int]]:
        """Todos los eventos, aun en cero, para que el tablero no cambie de forma."""
        with self._candado:
            return {evento.value: dict(conteo) for evento, conteo in self._conteos.items()}
