from __future__ import annotations

import logging

from app.metricas import Evento, Metricas
from app.reintentos import PoliticaReintentos, crear_con_reintentos
from domain.puertos import CasoExterno
from tests.app.falsos import PlataformaFalsa

CASO = CasoExterno("GASES DEL ORINOCO", "REQ-001", None, None, None, "texto", "motivo")


def _crear(plataforma, esperas, metricas):
    return crear_con_reintentos(
        plataforma, CASO, "zendesk_simulada", PoliticaReintentos(), metricas, esperas.append
    )


def test_se_recupera_al_tercer_intento_con_espera_creciente():
    plataforma, esperas, metricas = PlataformaFalsa("ZD", fallas_pendientes=2), [], Metricas()
    resultado = _crear(plataforma, esperas, metricas)
    assert resultado.id_externo == "ZD-000001"
    assert resultado.intentos == 3
    assert esperas == [0.2, 0.4]
    assert metricas.contar(Evento.INTENTO_FALLIDO) == 2
    assert metricas.contar(Evento.CASO_CREADO, "GASES DEL ORINOCO") == 1


def test_agotados_los_intentos_devuelve_el_motivo_y_lo_registra(caplog):
    plataforma, esperas, metricas = PlataformaFalsa("ZD", fallas_pendientes=9), [], Metricas()
    with caplog.at_level(logging.WARNING):
        resultado = _crear(plataforma, esperas, metricas)
    assert resultado.id_externo is None
    assert resultado.motivo == "timeout de 5 s"
    assert plataforma.llamadas == 3
    assert esperas == [0.2, 0.4]
    assert metricas.contar(Evento.CASO_NO_CREADO, "GASES DEL ORINOCO") == 1
    assert "empresa=GASES DEL ORINOCO plataforma=zendesk_simulada" in caplog.text
    assert "intento=3/3 error=timeout de 5 s" in caplog.text
    assert "plataforma_agotada" in caplog.text
