from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx2
import pytest

from app.triage import CasoDeUsoTriage
from domain.contrato import Solicitud
from domain.puertos import ErrorLLM
from services.ajustes import AjustesLLM
from services.analizador_llm import (
    AnalizadorCompatibleOpenAI,
    armar_pedido,
    crear_analizador,
    interpretar_respuesta,
)
from services.configuracion_empresas import cargar_catalogo
from tests.app.falsos import PlataformaFalsa
from tests.domain.datos import TEXTO_INCOMPLETO, TEXTO_JUANA

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
MUESTRA = json.loads((FIXTURES / "groq_analisis_2026-11-17.json").read_text(encoding="utf-8"))
MUESTRA_F0 = json.loads((FIXTURES / "groq_respuesta_2026-11-17.json").read_text(encoding="utf-8"))
CATALOGO = cargar_catalogo()
GASES = CATALOGO.obtener("GASES DEL ORINOCO")
CLAVE = "clave-de-prueba"


def _respuesta_con(contenido: str, fin: str = "stop") -> dict:
    cuerpo = copy.deepcopy(MUESTRA["respuesta"])
    cuerpo["choices"][0]["message"]["content"] = contenido
    cuerpo["choices"][0]["finish_reason"] = fin
    return cuerpo


def _analizador(manejador) -> AnalizadorCompatibleOpenAI:
    return AnalizadorCompatibleOpenAI(
        "https://llm.prueba/openai/v1", "modelo-x", CLAVE, 1.0, httpx2.MockTransport(manejador)
    )


def test_esquema_estricto_con_las_categorias_de_la_empresa():
    pedido = armar_pedido("modelo-x", TEXTO_JUANA, GASES)
    formato = pedido["response_format"]["json_schema"]
    assert formato["strict"] is True
    esquema = formato["schema"]
    assert esquema["additionalProperties"] is False
    assert set(esquema["required"]) == set(esquema["properties"])
    assert esquema["properties"]["categoria"]["enum"] == list(GASES.nombres_categorias)
    assert pedido["messages"][1] == {"role": "user", "content": TEXTO_JUANA}


def test_muestra_real_de_req_001():
    analisis = interpretar_respuesta(MUESTRA["respuesta"])
    assert analisis.categoria == "Incidente técnico"
    assert analisis.informacion_suficiente is True
    assert (analisis.tipo_documento, analisis.numero_documento) == ("CC", "102045678")


def test_muestra_de_f0_sin_los_campos_nuevos_es_error():
    with pytest.raises(ErrorLLM, match="informacion_suficiente"):
        interpretar_respuesta(MUESTRA_F0["respuesta"])


@pytest.mark.parametrize(
    ("contenido", "fin", "motivo"),
    [
        ("no es json", "stop", "esquema"),
        ('{"categoria": "Consulta"}', "stop", "esquema"),
        (
            '{"categoria": "Consulta", "informacion_suficiente": "si", "hechos": null, '
            '"tipo_documento": null, "numero_documento": null}',
            "stop",
            "informacion_suficiente",
        ),
        ('{"categoria": "Consu', "length", "incompleta"),
    ],
)
def test_salida_invalida_es_error(contenido, fin, motivo):
    with pytest.raises(ErrorLLM, match=motivo):
        interpretar_respuesta(_respuesta_con(contenido, fin))


def test_pedido_por_http_con_la_clave_en_el_encabezado():
    pedidos: list[httpx2.Request] = []

    def manejador(pedido: httpx2.Request) -> httpx2.Response:
        pedidos.append(pedido)
        return httpx2.Response(200, json=MUESTRA["respuesta"])

    analisis = _analizador(manejador).analizar(TEXTO_JUANA, GASES)
    assert analisis.categoria == "Incidente técnico"
    assert str(pedidos[0].url) == "https://llm.prueba/openai/v1/chat/completions"
    assert pedidos[0].headers["authorization"] == f"Bearer {CLAVE}"
    assert json.loads(pedidos[0].content)["model"] == "modelo-x"


@pytest.mark.parametrize(
    ("manejador", "motivo"),
    [
        (lambda p: httpx2.Response(429, json={"error": "limite"}), "HTTP 429"),
        (lambda p: httpx2.Response(200, content=b"<html>"), "no es JSON"),
    ],
)
def test_fallas_http_son_error(manejador, motivo):
    with pytest.raises(ErrorLLM, match=motivo):
        _analizador(manejador).analizar(TEXTO_JUANA, GASES)


def test_timeout_es_error():
    def manejador(pedido):
        raise httpx2.ReadTimeout("lento", request=pedido)

    with pytest.raises(ErrorLLM, match="timeout"):
        _analizador(manejador).analizar(TEXTO_JUANA, GASES)


def test_sin_clave_o_desactivado_no_hay_analizador():
    assert crear_analizador(AjustesLLM(llm_proveedor="ninguno", groq_api_key=CLAVE)) is None
    assert crear_analizador(AjustesLLM(llm_proveedor="groq", groq_api_key="  ")) is None
    con_clave = crear_analizador(AjustesLLM(llm_proveedor="groq", groq_api_key=CLAVE))
    assert isinstance(con_clave, AnalizadorCompatibleOpenAI)


def _triage(manejador) -> tuple[CasoDeUsoTriage, dict]:
    plataformas = {n: PlataformaFalsa("EXT") for n in CATALOGO.nombres}
    return CasoDeUsoTriage(CATALOGO, plataformas, _analizador(manejador)), plataformas


def test_triage_con_el_llm_caido_sigue_por_reglas():
    triage, _ = _triage(lambda p: httpx2.Response(503))
    resultado = triage.ejecutar(Solicitud("GASES DEL ORINOCO", "REQ-001", TEXTO_JUANA))
    assert resultado.solicitud_tipo == "Incidente técnico"
    assert resultado.solicitud_id_cliente == "102045678"


def test_sin_informacion_el_llm_no_impone_categoria():
    contenido = (
        '{"categoria": "Incidente técnico", "informacion_suficiente": false, '
        '"hechos": null, "tipo_documento": null, "numero_documento": null}'
    )
    triage, plataformas = _triage(lambda p: httpx2.Response(200, json=_respuesta_con(contenido)))
    resultado = triage.ejecutar(Solicitud("GASES DEL ORINOCO", "REQ-002", TEXTO_INCOMPLETO))
    assert resultado.proximo_paso.value == "CIERRE_POR_INFORMACION_INSUFICIENTE"
    assert resultado.solicitud_tipo is None
    assert plataformas["GASES DEL ORINOCO"].casos == []
