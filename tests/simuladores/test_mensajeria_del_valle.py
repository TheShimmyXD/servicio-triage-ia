from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from simuladores.mensajeria_del_valle.servicio import aplicacion


@pytest.fixture
def cliente():
    return TestClient(aplicacion)


@pytest.mark.parametrize(
    ("tipo_documento", "numero", "tipo_solicitud", "esperada"),
    [
        ("CC", "52000111", "Paquete dañado o perdido", "Alta"),
        ("CC", "52000111", "Envío retrasado", "Media"),
        ("CC", "52000111", "Consulta de rastreo", "Baja"),
        ("CC", "52000111", None, "Baja"),
        ("NIT", "800200300", "Consulta de rastreo", "Media"),
        ("CC", "1144556677", "Envío retrasado", "Alta"),
        ("NIT", "800200300", "Paquete dañado o perdido", "Alta"),
    ],
)
def test_reglas_del_simulador(cliente, tipo_documento, numero, tipo_solicitud, esperada):
    pedido = {
        "tipo_documento": tipo_documento,
        "numero_documento_cliente": numero,
        "tipo_solicitud": tipo_solicitud,
    }
    respuesta = cliente.post("/prioridad", json=pedido)
    assert respuesta.status_code == 200
    assert respuesta.json()["prioridad"] == esperada


def test_sin_documento_rechaza_el_pedido(cliente):
    respuesta = cliente.post("/prioridad", json={"tipo_solicitud": "Envío retrasado"})
    assert respuesta.status_code == 422
