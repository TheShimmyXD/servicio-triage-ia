"""Repositorio de solicitudes atendidas en memoria del proceso.

Alcanza para una instancia. Con varias instancias, o para no perder la memoria al
reiniciar, se cambia por una tabla con clave única (compania, solicitud_id) sin tocar
el triage: solo implementa el mismo puerto.
"""

from __future__ import annotations

import threading

from domain.duplicados import SolicitudAtendida


class RepositorioSolicitudesMemoria:
    def __init__(self) -> None:
        self._registros: dict[tuple[str, str], SolicitudAtendida] = {}
        self._candado = threading.Lock()

    def obtener(self, compania: str, solicitud_id: str) -> SolicitudAtendida | None:
        with self._candado:
            return self._registros.get((compania, solicitud_id))

    def guardar(self, compania: str, solicitud_id: str, atendida: SolicitudAtendida) -> None:
        with self._candado:
            self._registros[(compania, solicitud_id)] = atendida

    def __len__(self) -> int:
        return len(self._registros)
