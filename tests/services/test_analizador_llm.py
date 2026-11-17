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
    armar_instrucciones,
    armar_pedido,
    crear_analizador,
    interpretar_respuesta,
)
from services.configuracion_empresas import cargar_catalogo
from services.repositorio_memoria import RepositorioSolicitudesMemoria
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


def test_el_motivo_trae_el_codigo_de_groq_y_no_el_mensaje():
    cuerpo = {
        "error": {
            "message": "Failed to validate JSON: Juana 102045678",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": '{"categoria": "Juana 102045678"}',
        }
    }
    with pytest.raises(ErrorLLM) as error:
        _analizador(lambda p: httpx2.Response(400, json=cuerpo)).analizar(TEXTO_JUANA, GASES)
    assert str(error.value) == "HTTP 400 json_validate_failed"


@pytest.mark.parametrize(
    ("cuerpo", "motivo"),
    [
        ({"error": {"type": "rate_limit_error"}}, "HTTP 429 rate_limit_error"),
        ({"error": {"code": "Juana tiene cédula 102045678"}}, "HTTP 429"),
        ({"error": {"code": "x" * 65}}, "HTTP 429"),
        ({"error": "limite"}, "HTTP 429"),
        (["no", "es", "objeto"], "HTTP 429"),
    ],
)
def test_un_codigo_que_no_es_identificador_no_pasa_al_motivo(cuerpo, motivo):
    with pytest.raises(ErrorLLM) as error:
        _analizador(lambda p: httpx2.Response(429, json=cuerpo)).analizar(TEXTO_JUANA, GASES)
    assert str(error.value) == motivo


def test_un_error_sin_json_queda_solo_con_el_estado():
    with pytest.raises(ErrorLLM) as error:
        _analizador(lambda p: httpx2.Response(503, content=b"<html>")).analizar(TEXTO_JUANA, GASES)
    assert str(error.value) == "HTTP 503"


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
    caso_de_uso = CasoDeUsoTriage(
        CATALOGO, plataformas, _analizador(manejador), repositorio=RepositorioSolicitudesMemoria()
    )
    return caso_de_uso, plataformas


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


def test_instrucciones_con_la_excepcion_por_categoria():
    instrucciones = armar_instrucciones(GASES)
    assert "cuándo ocurrió" in instrucciones
    assert (
        "Si la categoría es Consulta informativa, basta con saber:\n"
        "- qué necesita o pide el cliente"
    ) in instrucciones
