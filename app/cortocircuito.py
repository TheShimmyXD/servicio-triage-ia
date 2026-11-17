"""Cortocircuitos: si un servicio de afuera está caído, se deja de esperarlo.

Sin ellos, cada solicitud espera el timeout completo (y los reintentos) antes de
resolverse con reglas. Tras `fallas_para_abrir` fallas seguidas el circuito se abre y,
durante `pausa_s` segundos, falla de inmediato sin llamar; el caso de uso responde con
reglas como ante cualquier falla de ese servicio. Pasada la pausa deja pasar una llamada
de prueba: si responde, se cierra; si falla, se abre otra vez.

`Cortocircuito` guarda solo el estado; los envoltorios del LLM y del servicio de
prioridad del cliente lo usan sin repetir esa lógica.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from domain.contrato import DocumentoCliente, Prioridad
from domain.empresa import ConfiguracionEmpresa
from domain.puertos import (
    AnalisisLLM,
    AnalizadorLLM,
    ErrorLLM,
    ErrorProveedorPrioridad,
    ErrorProveedorPrioridadSinRespuesta,
    ProveedorPrioridad,
)

registro = logging.getLogger(__name__)


@dataclass
class Cortocircuito:
    """Cuenta las fallas seguidas de un servicio y decide si vale la pena llamarlo."""

    fallas_para_abrir: int = 3
    pausa_s: float = 30.0
    reloj: Callable[[], float] = time.monotonic
    """Las pruebas lo reemplazan para no esperar la pausa."""
    servicio: str = "llm"
    """Solo para el log: qué servicio se dejó de llamar."""
    _fallas_seguidas: int = field(default=0, init=False)
    _abierto_hasta: float | None = field(default=None, init=False)
    _candado: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def abierto(self) -> bool:
        with self._candado:
            return self._abierto_hasta is not None and self.reloj() < self._abierto_hasta

    def registrar_exito(self) -> None:
        with self._candado:
            if self._abierto_hasta is not None:
                registro.info("cortocircuito_cerrado servicio=%s", self.servicio)
            self._fallas_seguidas = 0
            self._abierto_hasta = None

    def registrar_falla(self) -> None:
        with self._candado:
            self._fallas_seguidas += 1
            # Tras la pausa, una sola falla de la llamada de prueba basta para reabrir.
            if self._fallas_seguidas >= self.fallas_para_abrir or self._abierto_hasta is not None:
                self._abierto_hasta = self.reloj() + self.pausa_s
                registro.warning(
                    "cortocircuito_abierto servicio=%s fallas_seguidas=%d pausa_s=%.0f",
                    self.servicio,
                    self._fallas_seguidas,
                    self.pausa_s,
                )


@dataclass
class AnalizadorConCortocircuito:
    """Cumple el puerto AnalizadorLLM envolviendo al analizador real."""

    analizador: AnalizadorLLM
    fallas_para_abrir: int = 3
    pausa_s: float = 30.0
    reloj: Callable[[], float] = time.monotonic
    _circuito: Cortocircuito = field(init=False)

    def __post_init__(self) -> None:
        self._circuito = Cortocircuito(self.fallas_para_abrir, self.pausa_s, self.reloj, "llm")

    @property
    def abierto(self) -> bool:
        return self._circuito.abierto

    def analizar(self, texto: str, empresa: ConfiguracionEmpresa) -> AnalisisLLM:
        if self._circuito.abierto:
            raise ErrorLLM("cortocircuito abierto: se usan las reglas sin llamar al LLM")
        try:
            analisis = self.analizador.analizar(texto, empresa)
        except ErrorLLM:
            self._circuito.registrar_falla()
            raise
        self._circuito.registrar_exito()
        return analisis


@dataclass
class ProveedorConCortocircuito:
    """Cumple el puerto ProveedorPrioridad con un circuito por empresa.

    Cada cliente tiene su propio servicio, así que la caída de uno no debe dejar de
    consultar los demás; N y X salen del bloque proveedor_prioridad de su YAML. Solo el
    "no respondió" cuenta como falla: un rechazo o una respuesta inválida prueban que el
    servicio está vivo, y una solicitud sin documento ni siquiera lo llama.
    """

    proveedor: ProveedorPrioridad
    reloj: Callable[[], float] = time.monotonic
    _circuitos: dict[str, Cortocircuito] = field(default_factory=dict, init=False)
    _candado: threading.Lock = field(default_factory=threading.Lock, init=False)

    def circuito(self, empresa: ConfiguracionEmpresa) -> Cortocircuito:
        with self._candado:
            if empresa.nombre not in self._circuitos:
                configuracion = empresa.proveedor_prioridad
                self._circuitos[empresa.nombre] = Cortocircuito(
                    configuracion.fallas_para_abrir,
                    configuracion.pausa_s,
                    self.reloj,
                    f"prioridad:{empresa.nombre}",
                )
            return self._circuitos[empresa.nombre]

    def obtener(
        self,
        empresa: ConfiguracionEmpresa,
        documento: DocumentoCliente | None,
        categoria: str | None,
    ) -> Prioridad:
        circuito = self.circuito(empresa)
        if circuito.abierto:
            raise ErrorProveedorPrioridad(
                "no respondió en las últimas consultas; se volverá a consultar en unos segundos"
            )
        try:
            prioridad = self.proveedor.obtener(empresa, documento, categoria)
        except ErrorProveedorPrioridadSinRespuesta:
            circuito.registrar_falla()
            raise
        circuito.registrar_exito()
        return prioridad
