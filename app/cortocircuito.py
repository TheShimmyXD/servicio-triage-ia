"""Cortocircuito del LLM: si el proveedor está caído, se deja de esperarlo.

Sin él, cada solicitud espera el timeout completo antes de resolverse con reglas. Tras
`fallas_para_abrir` fallas seguidas el circuito se abre y, durante `pausa_s` segundos,
falla de inmediato sin llamar; el caso de uso responde con reglas como ante cualquier
ErrorLLM. Pasada la pausa deja pasar una llamada de prueba: si responde, se cierra; si
falla, se abre otra vez.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from domain.empresa import ConfiguracionEmpresa
from domain.puertos import AnalisisLLM, AnalizadorLLM, ErrorLLM

registro = logging.getLogger(__name__)


@dataclass
class AnalizadorConCortocircuito:
    """Cumple el puerto AnalizadorLLM envolviendo al analizador real."""

    analizador: AnalizadorLLM
    fallas_para_abrir: int = 3
    pausa_s: float = 30.0
    reloj: Callable[[], float] = time.monotonic
    """Las pruebas lo reemplazan para no esperar la pausa."""
    _fallas_seguidas: int = field(default=0, init=False)
    _abierto_hasta: float | None = field(default=None, init=False)
    _candado: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def abierto(self) -> bool:
        with self._candado:
            return self._abierto_hasta is not None and self.reloj() < self._abierto_hasta

    def analizar(self, texto: str, empresa: ConfiguracionEmpresa) -> AnalisisLLM:
        with self._candado:
            if self._abierto_hasta is not None and self.reloj() < self._abierto_hasta:
                raise ErrorLLM("cortocircuito abierto: se usan las reglas sin llamar al LLM")
        try:
            analisis = self.analizador.analizar(texto, empresa)
        except ErrorLLM:
            self._registrar_falla()
            raise
        with self._candado:
            if self._abierto_hasta is not None:
                registro.info("cortocircuito_cerrado: el LLM volvió a responder")
            self._fallas_seguidas = 0
            self._abierto_hasta = None
        return analisis

    def _registrar_falla(self) -> None:
        with self._candado:
            self._fallas_seguidas += 1
            # Tras la pausa, una sola falla de la llamada de prueba basta para reabrir.
            if self._fallas_seguidas >= self.fallas_para_abrir or self._abierto_hasta is not None:
                self._abierto_hasta = self.reloj() + self.pausa_s
                registro.warning(
                    "cortocircuito_abierto fallas_seguidas=%d pausa_s=%.0f",
                    self._fallas_seguidas,
                    self.pausa_s,
                )
