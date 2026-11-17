from __future__ import annotations

from fastapi.testclient import TestClient

from entrypoints.api.principal import aplicacion


def test_salud_responde_ok():
    cliente = TestClient(aplicacion)
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
