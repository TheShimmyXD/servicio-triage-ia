"""Plataformas de casos simuladas y su registro por nombre.

Cada empresa nombra su plataforma en el YAML (por ejemplo, "zendesk_simulada" con
prefijo "ZD") y el registro la arma: nadie pregunta por la empresa. Un adaptador real
se suma al registro con su nombre y no toca el triage.

Para probar el manejo de errores, el simulado acepta fallas en sus parámetros:
"fallas_iniciales" (las primeras N llamadas fallan) y "probabilidad_falla" (0 a 1).
"""

from __future__ import annotations

import random
import threading
from collections.abc import Callable, Mapping
from typing import Any

from domain.empresa import ConfiguracionPlataforma
from domain.puertos import CasoExterno, ErrorPlataforma, PlataformaCasos

SUFIJO_SIMULADA = "_simulada"


class PlataformaDesconocida(LookupError):
    """El YAML nombra una plataforma que no está en el registro. Detiene el arranque."""


class ParametrosPlataformaInvalidos(ValueError):
    """Un parámetro de la plataforma en el YAML no tiene sentido. Detiene el arranque."""


class PlataformaSimulada:
    """Guarda los casos en memoria y devuelve ids ficticios con el prefijo (ZD-000001)."""

    def __init__(
        self,
        nombre: str,
        prefijo: str,
        fallas_iniciales: int = 0,
        probabilidad_falla: float = 0.0,
        aleatorio: random.Random | None = None,
    ) -> None:
        self.nombre = nombre
        self.prefijo = prefijo
        self.casos: list[CasoExterno] = []
        self.llamadas = 0
        self.fallas_pendientes = fallas_iniciales
        self.probabilidad_falla = probabilidad_falla
        self._aleatorio = aleatorio or random.Random()
        # FastAPI atiende los endpoints síncronos en varios hilos: el contador no debe repetirse.
        self._candado = threading.Lock()

    def crear_caso(self, caso: CasoExterno) -> str:
        with self._candado:
            self.llamadas += 1
            if self.fallas_pendientes > 0:
                self.fallas_pendientes -= 1
                raise ErrorPlataforma(f"{self.nombre} no respondió (falla simulada)")
            if self.probabilidad_falla and self._aleatorio.random() < self.probabilidad_falla:
                raise ErrorPlataforma(f"{self.nombre} respondió 503 (falla simulada)")
            self.casos.append(caso)
            return f"{self.prefijo}-{len(self.casos):06d}"


FabricaPlataforma = Callable[[str, Mapping[str, Any]], PlataformaCasos]


def _crear_simulada(nombre: str, parametros: Mapping[str, Any]) -> PlataformaCasos:
    # Sin prefijo en el YAML se usa el nombre de la plataforma (zendesk_simulada -> ZENDESK).
    prefijo = str(parametros.get("prefijo") or nombre.removesuffix(SUFIJO_SIMULADA))
    try:
        fallas = int(parametros.get("fallas_iniciales", 0))
        probabilidad = float(parametros.get("probabilidad_falla", 0.0))
    except (TypeError, ValueError) as error:
        raise ParametrosPlataformaInvalidos(f"{nombre}: {error}") from error
    if fallas < 0 or not 0.0 <= probabilidad <= 1.0:
        raise ParametrosPlataformaInvalidos(
            f"{nombre}: fallas_iniciales debe ser >= 0 y probabilidad_falla estar entre 0 y 1"
        )
    return PlataformaSimulada(nombre, prefijo.strip().upper(), fallas, probabilidad)


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
