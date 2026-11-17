"""Juana y la solicitud incompleta recorren todo el dominio, sin LLM ni red."""

from __future__ import annotations

from datetime import date

from domain.contrato import ResultadoTriage, Solicitud
from domain.documento_cliente import extraer_documento
from domain.informacion_minima import evaluar_informacion_minima, extraer_hecho_principal
from domain.justificacion import construir_justificacion
from domain.prioridad import calcular_prioridad
from domain.proximo_paso import decidir_proximo_paso, estado_para
from tests.domain.datos import DELEGACIONES_GAS, REGLAS_GAS, TEXTO_INCOMPLETO, TEXTO_JUANA

FECHA = date(2026, 11, 17)

# Nombres y orden del ejemplo de OUTPUT; fecha en minúscula y cada valor en su campo (README).
CAMPOS_DEL_CONTRATO = [
    "compania",
    "solicitud_id",
    "solicitud_fecha",
    "solicitud_tipo",
    "solicitud_prioridad",
    "solicitud_id_cliente",
    "solicitud_tipo_id_cliente",
    "solicitud_id_plataforma_externa",
    "proximo_paso",
    "justificacion",
    "estado",
]


def _triage_de_dominio(solicitud: Solicitud, categoria: str) -> ResultadoTriage:
    """Encadena las reglas como lo hará el caso de uso, con la categoría ya decidida."""
    evaluacion = evaluar_informacion_minima(solicitud.solicitud_descripcion)
    paso = decidir_proximo_paso(evaluacion.suficiente, categoria, DELEGACIONES_GAS)
    documento = extraer_documento(solicitud.solicitud_descripcion)
    decision = (
        calcular_prioridad(categoria, solicitud.solicitud_descripcion, REGLAS_GAS)
        if evaluacion.suficiente
        else None
    )
    hecho = extraer_hecho_principal(solicitud.solicitud_descripcion)
    return ResultadoTriage(
        compania=solicitud.compania,
        solicitud_id=solicitud.solicitud_id,
        solicitud_fecha=FECHA,
        solicitud_tipo=categoria if evaluacion.suficiente else None,
        solicitud_prioridad=decision.prioridad if decision else None,
        solicitud_tipo_id_cliente=documento.tipo if documento else None,
        solicitud_id_cliente=documento.numero if documento else None,
        solicitud_id_plataforma_externa=None,
        proximo_paso=paso,
        justificacion=construir_justificacion(paso, categoria, decision, hecho),
        estado=estado_para(paso),
    )


def test_salida_tiene_los_campos_del_contrato():
    solicitud = Solicitud("GASES DEL ORINOCO", "REQ-001", TEXTO_JUANA)
    salida = _triage_de_dominio(solicitud, "Incidente técnico").a_diccionario()
    assert sorted(salida) == sorted(CAMPOS_DEL_CONTRATO)


def test_juana_de_punta_a_punta_en_el_dominio():
    solicitud = Solicitud("GASES DEL ORINOCO", "REQ-001", TEXTO_JUANA)
    salida = _triage_de_dominio(solicitud, "Incidente técnico").a_diccionario()
    assert salida["solicitud_fecha"] == "2026-11-17"
    assert salida["solicitud_tipo"] == "Incidente técnico"
    assert salida["solicitud_prioridad"] == "Alta"
    assert salida["solicitud_tipo_id_cliente"] == "CC"
    assert salida["solicitud_id_cliente"] == "102045678"
    assert salida["proximo_paso"] == "GESTION_EXTERNA"
    assert salida["estado"] == "pendiente"
    assert "estufa" in salida["justificacion"]


def test_incompleta_de_punta_a_punta_en_el_dominio():
    solicitud = Solicitud("GASES DEL ORINOCO", "REQ-002", TEXTO_INCOMPLETO)
    salida = _triage_de_dominio(solicitud, "Consulta").a_diccionario()
    assert salida["proximo_paso"] == "CIERRE_POR_INFORMACION_INSUFICIENTE"
    assert salida["justificacion"] == "Información incompleta o faltante"
    assert salida["estado"] == "cerrado"
    assert salida["solicitud_prioridad"] is None
