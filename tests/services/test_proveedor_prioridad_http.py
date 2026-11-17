from __future__ import annotations

import json

import httpx2
import pytest

from app.triage import CasoDeUsoTriage
from domain.contrato import DocumentoCliente, Prioridad, Solicitud
from domain.puertos import ErrorProveedorPrioridad
from services.configuracion_empresas import cargar_catalogo
from services.proveedor_prioridad_http import ProveedorPrioridadHTTP
from services.repositorio_memoria import RepositorioSolicitudesMemoria
from simuladores.mensajeria_del_valle.servicio import PedidoPrioridad, calcular_prioridad_cliente
from tests.app.falsos import PlataformaFalsa

CATALOGO = cargar_catalogo()
MDV = CATALOGO.obtener("MENSAJERIA DEL VALLE")
DOCUMENTO = DocumentoCliente("CC", "52000111")
TEXTO_MDV = (
    "Mi paquete no ha llegado y ya pasó una semana desde la fecha prometida, necesito "
    "saber qué pasó. Mi cédula es 1144556677"
)


def _simulador(pedido: httpx2.Request) -> httpx2.Response:
    """Responde como el simulador de MDV, sin levantar el servidor."""
    respuesta = calcular_prioridad_cliente(PedidoPrioridad(**json.loads(pedido.content)))
    return httpx2.Response(200, json=respuesta.model_dump())


def _proveedor(manejador, esperas=None):
    dormir = esperas.append if esperas is not None else (lambda _: None)
    return ProveedorPrioridadHTTP(httpx2.MockTransport(manejador), dormir)


def test_envia_el_contrato_del_cliente_y_devuelve_su_prioridad():
    pedidos: list[httpx2.Request] = []

    def manejador(pedido):
        pedidos.append(pedido)
        return _simulador(pedido)

    prioridad = _proveedor(manejador).obtener(MDV, DOCUMENTO, "Paquete dañado o perdido")
    assert prioridad is Prioridad.ALTA
    assert str(pedidos[0].url) == "http://127.0.0.1:8001/prioridad"
    assert json.loads(pedidos[0].content) == {
        "tipo_documento": "CC",
        "numero_documento_cliente": "52000111",
        "tipo_solicitud": "Paquete dañado o perdido",
    }


def test_reintenta_ante_503_y_se_recupera():
    respuestas = iter([httpx2.Response(503), httpx2.Response(200, json={"prioridad": "Baja"})])
    esperas: list[float] = []
    proveedor = _proveedor(lambda _: next(respuestas), esperas)
    assert proveedor.obtener(MDV, DOCUMENTO, None) is Prioridad.BAJA
    assert esperas == [0.2]


def test_servicio_apagado_agota_los_reintentos_del_yaml():
    llamadas = []

    def apagado(pedido):
        llamadas.append(pedido)
        raise httpx2.ConnectError("conexión rechazada", request=pedido)

    esperas: list[float] = []
    with pytest.raises(ErrorProveedorPrioridad, match="no respondió tras 3 intentos"):
        _proveedor(apagado, esperas).obtener(MDV, DOCUMENTO, "Envío retrasado")
    assert len(llamadas) == MDV.proveedor_prioridad.reintentos + 1
    assert esperas == [0.2, 0.4]


def test_un_4xx_no_se_reintenta():
    llamadas = []

    def rechazo(pedido):
        llamadas.append(pedido)
        return httpx2.Response(422, json={"detail": "x"})

    with pytest.raises(ErrorProveedorPrioridad, match="HTTP 422"):
        _proveedor(rechazo).obtener(MDV, DOCUMENTO, None)
    assert len(llamadas) == 1


def test_prioridad_fuera_del_contrato_se_rechaza():
    proveedor = _proveedor(lambda _: httpx2.Response(200, json={"prioridad": "Urgentísima"}))
    with pytest.raises(ErrorProveedorPrioridad, match="sin una prioridad válida"):
        proveedor.obtener(MDV, DOCUMENTO, None)


def test_sin_documento_no_llama_al_servicio():
    with pytest.raises(ErrorProveedorPrioridad, match="documento"):
        _proveedor(lambda _: pytest.fail("no debía llamar")).obtener(MDV, None, None)


def _triage(proveedor):
    plataformas = {nombre: PlataformaFalsa("EXT") for nombre in CATALOGO.nombres}
    return CasoDeUsoTriage(
        CATALOGO,
        plataformas,
        proveedores_prioridad={"http": proveedor},
        repositorio=RepositorioSolicitudesMemoria(),
    )


def test_triage_con_el_servicio_arriba_usa_su_prioridad():
    resultado = _triage(_proveedor(_simulador)).ejecutar(
        Solicitud("MENSAJERIA DEL VALLE", "M-10", TEXTO_MDV)
    )
    # Reglas de la empresa: Media. El cliente es preferente en el simulador: Alta.
    assert resultado.solicitud_prioridad is Prioridad.ALTA
    assert "fuente: servicio del cliente" in resultado.justificacion


def test_triage_con_el_servicio_apagado_usa_las_reglas_y_lo_dice():
    def apagado(pedido):
        raise httpx2.ConnectError("conexión rechazada", request=pedido)

    resultado = _triage(_proveedor(apagado)).ejecutar(
        Solicitud("MENSAJERIA DEL VALLE", "M-11", TEXTO_MDV)
    )
    assert resultado.solicitud_prioridad is Prioridad.MEDIA
    assert "no se usó el servicio de prioridad del cliente" in resultado.justificacion
    assert "reglas de la empresa" in resultado.justificacion
