from __future__ import annotations

import shutil
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.composicion import construir_triage
from entrypoints.api.esquemas import EJEMPLO_REQ_001
from entrypoints.api.principal import crear_aplicacion
from services.configuracion_empresas import CARPETA_POR_DEFECTO

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


def test_las_respuestas_declaran_utf8(cliente):
    # Clientes como PowerShell 5.1 leen Latin-1 si el charset no viene en el encabezado.
    exito = cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    error = cliente.post("/solicitudes", json={**EJEMPLO_REQ_001, "compania": "OTRA"})
    for respuesta in (exito, error, cliente.get("/empresas"), cliente.get("/metricas")):
        assert respuesta.headers["content-type"] == "application/json; charset=utf-8"


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


def test_mismo_id_con_otro_texto_da_409(cliente):
    assert cliente.post("/solicitudes", json=EJEMPLO_REQ_001).status_code == 200
    otra = {**EJEMPLO_REQ_001, "solicitud_descripcion": "Quiero cambiar mi plan"}
    respuesta = cliente.post("/solicitudes", json=otra)
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "SOLICITUD_DUPLICADA"


def test_metricas_cuentan_casos_y_duplicados(cliente):
    cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    metricas = cliente.get("/metricas").json()
    assert metricas["casos_creados"] == {"GASES DEL ORINOCO": 1}
    assert metricas["duplicados_devueltos"] == {"GASES DEL ORINOCO": 1}
    assert metricas["casos_no_creados"] == {}


def test_plataforma_caida_desde_el_yaml_no_tumba_la_respuesta(tmp_path):
    for archivo in CARPETA_POR_DEFECTO.glob("*.yaml"):
        shutil.copy(archivo, tmp_path)
    gases = tmp_path / "gases_del_orinoco.yaml"
    texto = gases.read_text(encoding="utf-8").replace(
        "prefijo: ZD", "prefijo: ZD\n    probabilidad_falla: 1"
    )
    gases.write_text(texto, encoding="utf-8")
    triage = construir_triage(tmp_path)
    triage.dormir = lambda _: None
    cliente = TestClient(crear_aplicacion(triage))
    respuesta = cliente.post("/solicitudes", json=EJEMPLO_REQ_001)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "error_plataforma"
    assert cuerpo["solicitud_id_plataforma_externa"] is None
    assert "zendesk_simulada" in cuerpo["justificacion"]
    metricas = cliente.get("/metricas").json()
    assert metricas["intentos_fallidos_plataforma"] == {"GASES DEL ORINOCO": 3}
    assert metricas["casos_no_creados"] == {"GASES DEL ORINOCO": 1}
