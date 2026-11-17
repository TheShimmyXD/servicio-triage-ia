from __future__ import annotations

from domain.contrato import Prioridad
from domain.prioridad import FUENTE_REGLAS, calcular_prioridad
from tests.domain.datos import REGLAS_GAS, TEXTO_JUANA


def test_juana_sube_a_alta_por_urgente():
    decision = calcular_prioridad("Incidente técnico", TEXTO_JUANA, REGLAS_GAS)
    assert decision.prioridad is Prioridad.ALTA
    assert "urgente" in decision.motivo
    assert decision.fuente == FUENTE_REGLAS


def test_sin_senal_queda_la_base_de_la_categoria():
    decision = calcular_prioridad("Incidente técnico", "La estufa falla desde ayer", REGLAS_GAS)
    assert decision.prioridad is Prioridad.MEDIA
    assert "Incidente técnico" in decision.motivo


def test_categoria_desconocida_usa_la_prioridad_por_defecto():
    decision = calcular_prioridad("Otra", "texto cualquiera", REGLAS_GAS)
    assert decision.prioridad is Prioridad.BAJA


def test_una_senal_menor_no_baja_la_base():
    decision = calcular_prioridad("Incidente técnico", "pongo un reclamo", REGLAS_GAS)
    assert decision.prioridad is Prioridad.MEDIA


def test_senal_de_varias_palabras_sin_tildes_ni_mayusculas():
    decision = calcular_prioridad("Consulta", "Hay una FUGA DE GAS en la cocina", REGLAS_GAS)
    assert decision.prioridad is Prioridad.ALTA


def test_senal_solo_con_palabra_completa():
    # "riesgos" contiene "riesgo" pero no es la misma palabra; la regla es exacta.
    decision = calcular_prioridad("Consulta", "consulto por los riesgosos", REGLAS_GAS)
    assert decision.prioridad is Prioridad.BAJA
