from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.composicion import construir_triage
from entrypoints.api.esquemas import EJEMPLO_REQ_001
from entrypoints.api.principal import crear_aplicacion

HOY = date(2026, 11, 17)
CAMPOS_SALIDA = [
    "compania",
    "solicitud_id",
    "solicitud_fecha",
    "solicitud_tipo",
    "solicitud_prioridad",
    "solicitud_tipo_id_cliente",
    "solicitud_id_cliente",
    "solicitud_id_plataforma_externa",
    "proximo_paso",
    "justificacion",
    "estado",
]


@pytest.fixture
def cliente():
    triage = construir_triage()
    triage.hoy = lambda: HOY
    return TestClient(crear_aplicacion(triage))


def test_req_001_devuelve_el_contrato_completo(cliente):
    respuesta = cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert list(cuerpo) == CAMPOS_SALIDA
    assert cuerpo["compania"] == "GASES DEL ORINOCO"
    assert cuerpo["solicitud_id"] == "REQ-001"
    assert cuerpo["solicitud_fecha"] == "2026-11-17"
    assert cuerpo["solicitud_tipo"] == "Incidente técnico"
    assert cuerpo["solicitud_prioridad"] == "Alta"
    assert cuerpo["solicitud_tipo_id_cliente"] == "CC"
    assert cuerpo["solicitud_id_cliente"] == "102045678"
    assert cuerpo["solicitud_id_plataforma_externa"] == "ZD-000001"
    assert cuerpo["proximo_paso"] == "GESTION_EXTERNA"
    assert cuerpo["justificacion"]
    assert cuerpo["estado"] == "pendiente"


def test_nombre_de_empresa_sin_importar_mayusculas_ni_espacios(cliente):
    entrada = {**EJEMPLO_REQ_001, "compania": "  gases   del orinoco "}
    respuesta = cliente.post("/solicitudes", json=entrada)
    assert respuesta.status_code == 200
    assert respuesta.json()["compania"] == "GASES DEL ORINOCO"


def test_empresa_desconocida_da_404_con_las_validas(cliente):
    entrada = {**EJEMPLO_REQ_001, "compania": "ACUEDUCTO DEL SUR"}
    respuesta = cliente.post("/solicitudes", json=entrada)
    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "EMPRESA_NO_PARAMETRIZADA"
    assert "ACUEDUCTO DEL SUR" in cuerpo["mensaje"]
    assert "GASES DEL ORINOCO" in cuerpo["empresas_validas"]
    assert len(cuerpo["empresas_validas"]) == 4


@pytest.mark.parametrize(
    ("entrada", "campo"),
    [
        ({"compania": "GASES DEL ORINOCO", "solicitud_id": "REQ-9"}, "solicitud_descripcion"),
        ({**EJEMPLO_REQ_001, "solicitud_descripcion": "   "}, "solicitud_descripcion"),
        ({**EJEMPLO_REQ_001, "solicitud_id": 7}, "solicitud_id"),
        ({**EJEMPLO_REQ_001, "solicitud_descripcion": "x" * 5001}, "solicitud_descripcion"),
    ],
)
def test_entrada_invalida_da_422_con_el_campo(cliente, entrada, campo):
    respuesta = cliente.post("/solicitudes", json=entrada)
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "ENTRADA_INVALIDA"
    assert campo in [e["campo"] for e in cuerpo["errores"]]


def test_cuerpo_que_no_es_json_da_422(cliente):
    respuesta = cliente.post(
        "/solicitudes", content="no es json", headers={"content-type": "application/json"}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "ENTRADA_INVALIDA"


def test_empresas_lista_las_parametrizadas(cliente):
    respuesta = cliente.get("/empresas")
    assert respuesta.status_code == 200
    assert respuesta.json()["empresas"] == [
        "GASES DEL ORINOCO",
        "MENSAJERIA DEL VALLE",
        "RED MOVIL ANDINA",
        "SALUD INTEGRAL DEL LLANO",
    ]


def test_cada_empresa_usa_el_prefijo_de_su_plataforma(cliente):
    cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    segunda = cliente.post("/solicitudes", json={**EJEMPLO_REQ_001, "solicitud_id": "REQ-002"})
    assert segunda.json()["solicitud_id_plataforma_externa"] == "ZD-000002"


def test_error_inesperado_da_500_con_codigo():
    triage = construir_triage()

    def _explota(_):
        raise RuntimeError("falla de prueba")

    triage.ejecutar = _explota
    cliente = TestClient(crear_aplicacion(triage), raise_server_exceptions=False)
    respuesta = cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    assert respuesta.status_code == 500
    assert respuesta.json()["codigo"] == "ERROR_INTERNO"
