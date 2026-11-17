"""Plataformas de casos simuladas y su registro por nombre.

Cada empresa nombra su plataforma en el YAML (por ejemplo, "zendesk_simulada" con
prefijo "ZD") y el registro la arma: nadie pregunta por la empresa. Un adaptador real
se suma al registro con su nombre y no toca el triage.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any

from domain.empresa import ConfiguracionPlataforma
from domain.puertos import CasoExterno, PlataformaCasos

SUFIJO_SIMULADA = "_simulada"


class PlataformaDesconocida(LookupError):
    """El YAML nombra una plataforma que no está en el registro. Detiene el arranque."""


class PlataformaSimulada:
    """Guarda los casos en memoria y devuelve ids ficticios con el prefijo (ZD-000001)."""

    def __init__(self, nombre: str, prefijo: str) -> None:
        self.nombre = nombre
        self.prefijo = prefijo
        self.casos: list[CasoExterno] = []
        # FastAPI atiende los endpoints síncronos en varios hilos: el contador no debe repetirse.
        self._candado = threading.Lock()

    def crear_caso(self, caso: CasoExterno) -> str:
        with self._candado:
            self.casos.append(caso)
            return f"{self.prefijo}-{len(self.casos):06d}"


FabricaPlataforma = Callable[[str, Mapping[str, Any]], PlataformaCasos]


def _crear_simulada(nombre: str, parametros: Mapping[str, Any]) -> PlataformaCasos:
    # Sin prefijo en el YAML se usa el nombre de la plataforma (zendesk_simulada -> ZENDESK).
    prefijo = str(parametros.get("prefijo") or nombre.removesuffix(SUFIJO_SIMULADA))
    return PlataformaSimulada(nombre, prefijo.strip().upper())


REGISTRO: dict[str, FabricaPlataforma] = {"simulada": _crear_simulada}
"""Adaptadores por nombre. Todo nombre terminado en "_simulada" usa el simulado genérico."""


def crear_plataforma(configuracion: ConfiguracionPlataforma) -> PlataformaCasos:
    nombre = configuracion.nombre
    fabrica = REGISTRO.get(nombre)
    if fabrica is None and nombre.endswith(SUFIJO_SIMULADA):
        fabrica = REGISTRO["simulada"]
    if fabrica is None:
        validas = ", ".join(sorted(REGISTRO))
        raise PlataformaDesconocida(
            f'Plataforma "{nombre}" sin adaptador. Registradas: {validas} '
            f'(o cualquier nombre terminado en "{SUFIJO_SIMULADA}")'
        )
    return fabrica(nombre, configuracion.parametros)
