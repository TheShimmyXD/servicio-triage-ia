from __future__ import annotations

from domain.contrato import Prioridad, ProximoPaso
from domain.justificacion import construir_justificacion
from domain.prioridad import DecisionPrioridad


def test_cierre_usa_el_texto_literal_del_enunciado():
    texto = construir_justificacion(
        ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE, None, None, None
    )
    assert texto == "Información incompleta o faltante"


def test_cita_el_hecho_la_prioridad_su_fuente_y_el_paso():
    decision = DecisionPrioridad(Prioridad.ALTA, 'la solicitud menciona "urgente"')
    texto = construir_justificacion(
        ProximoPaso.GESTION_EXTERNA, "Incidente técnico", decision, "la estufa presenta fallas"
    )
    assert texto.startswith('Incidente técnico: "la estufa presenta fallas".')
    assert "Prioridad Alta" in texto
    assert "urgente" in texto
    assert "reglas de la empresa" in texto
    assert "delegación externa" in texto


def test_respuesta_directa_sin_hecho():
    decision = DecisionPrioridad(Prioridad.BAJA, "prioridad por defecto de la empresa (Baja)")
    texto = construir_justificacion(ProximoPaso.RESPUESTA_DIRECTA, "Consulta", decision, None)
    assert texto.startswith("Consulta. Prioridad Baja")
    assert "responde directamente" in texto
