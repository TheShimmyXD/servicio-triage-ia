"""Creación del caso externo con reintentos y espera creciente.

Una caída breve de la plataforma (timeout, 503) no debe dejar el caso sin crear. Si se
agotan los intentos, quien llama recibe el motivo y decide; nada se lanza hacia la API.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.metricas import Evento, Metricas
from domain.puertos import CasoExterno, ErrorPlataforma, PlataformaCasos

registro = logging.getLogger(__name__)


@dataclass(frozen=True)
class PoliticaReintentos:
    intentos: int = 3
    espera_inicial: float = 0.2
    """Segundos antes del segundo intento; se multiplica por el factor en cada uno."""
    factor: float = 2.0

    def espera_tras(self, intento: int) -> float:
        """Espera después del intento N (1, 2, ...): 0.2 s, 0.4 s, ..."""
        return self.espera_inicial * self.factor ** (intento - 1)


@dataclass(frozen=True)
class ResultadoCreacion:
    id_externo: str | None
    intentos: int
    motivo: str | None = None


def crear_con_reintentos(
    plataforma: PlataformaCasos,
    caso: CasoExterno,
    nombre_plataforma: str,
    politica: PoliticaReintentos,
    metricas: Metricas,
    dormir: Callable[[float], None],
) -> ResultadoCreacion:
    motivo = ""
    for intento in range(1, politica.intentos + 1):
        try:
            id_externo = plataforma.crear_caso(caso)
        except ErrorPlataforma as error:
            motivo = str(error)
            metricas.sumar(Evento.INTENTO_FALLIDO, caso.compania)
            registro.warning(
                "plataforma_fallo empresa=%s plataforma=%s solicitud=%s intento=%d/%d error=%s",
                caso.compania,
                nombre_plataforma,
                caso.solicitud_id,
                intento,
                politica.intentos,
                motivo,
            )
            if intento < politica.intentos:
                dormir(politica.espera_tras(intento))
            continue
        metricas.sumar(Evento.CASO_CREADO, caso.compania)
        return ResultadoCreacion(id_externo, intento)

    metricas.sumar(Evento.CASO_NO_CREADO, caso.compania)
    registro.error(
        "plataforma_agotada empresa=%s plataforma=%s solicitud=%s intentos=%d error=%s",
        caso.compania,
        nombre_plataforma,
        caso.solicitud_id,
        politica.intentos,
        motivo,
    )
    return ResultadoCreacion(None, politica.intentos, motivo)
