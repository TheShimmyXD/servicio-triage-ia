from __future__ import annotations

from dataclasses import replace

import pytest

from app.cortocircuito import AnalizadorConCortocircuito, ProveedorConCortocircuito
from app.triage import CasoDeUsoTriage
from domain.contrato import DocumentoCliente, Prioridad, Solicitud
from domain.puertos import AnalisisLLM, ErrorLLM, ErrorProveedorPrioridad
from services.configuracion_empresas import cargar_catalogo
from services.repositorio_memoria import RepositorioSolicitudesMemoria
from tests.app.falsos import AnalizadorFalso, PlataformaFalsa, ProveedorPrioridadFalso
from tests.domain.datos import TEXTO_JUANA

CATALOGO = cargar_catalogo()
GAS = CATALOGO.obtener("GASES DEL ORINOCO")
MDV = CATALOGO.obtener("MENSAJERIA DEL VALLE")
DOCUMENTO = DocumentoCliente("CC", "1144556677")
TEXTO_MDV = (
    "Mi paquete no ha llegado y ya pasó una semana desde la fecha prometida, necesito "
    "saber qué pasó. Mi cédula es 1144556677"
)
ANALISIS = AnalisisLLM(
    categoria="Incidente técnico",
    informacion_suficiente=True,
    hechos="la estufa no hace contacto",
    tipo_documento="CC",
    numero_documento="102045678",
)


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


def _circuito(falso: AnalizadorFalso, reloj: Reloj) -> AnalizadorConCortocircuito:
    return AnalizadorConCortocircuito(falso, fallas_para_abrir=3, pausa_s=30, reloj=reloj)


def _fallar(circuito: AnalizadorConCortocircuito, veces: int) -> None:
    for _ in range(veces):
        with pytest.raises(ErrorLLM):
            circuito.analizar("texto", GAS)


def test_se_abre_tras_n_fallas_y_deja_de_llamar():
    falso, reloj = AnalizadorFalso(error="timeout"), Reloj()
    circuito = _circuito(falso, reloj)
    _fallar(circuito, 3)
    assert circuito.abierto and falso.llamados == 3
    _fallar(circuito, 5)
    assert falso.llamados == 3


def test_las_fallas_no_seguidas_no_lo_abren():
    falso, reloj = AnalizadorFalso(error="timeout"), Reloj()
    circuito = _circuito(falso, reloj)
    _fallar(circuito, 2)
    falso.error, falso.respuesta = None, ANALISIS
    assert circuito.analizar("texto", GAS) is ANALISIS
    falso.error = "timeout"
    _fallar(circuito, 2)
    assert not circuito.abierto


def test_tras_la_pausa_una_prueba_exitosa_lo_cierra():
    falso, reloj = AnalizadorFalso(error="timeout"), Reloj()
    circuito = _circuito(falso, reloj)
    _fallar(circuito, 3)
    reloj.ahora += 31
    falso.error, falso.respuesta = None, ANALISIS
    assert circuito.analizar("texto", GAS) is ANALISIS
    assert not circuito.abierto


def test_tras_la_pausa_una_prueba_fallida_lo_reabre():
    falso, reloj = AnalizadorFalso(error="timeout"), Reloj()
    circuito = _circuito(falso, reloj)
    _fallar(circuito, 3)
    reloj.ahora += 31
    _fallar(circuito, 1)
    assert circuito.abierto and falso.llamados == 4


def test_triage_con_llm_caido_responde_con_reglas_sin_llamarlo():
    falso = AnalizadorFalso(error="timeout")
    triage = CasoDeUsoTriage(
        CATALOGO,
        {nombre: PlataformaFalsa("EXT") for nombre in CATALOGO.nombres},
        _circuito(falso, Reloj()),
        repositorio=RepositorioSolicitudesMemoria(),
    )
    for numero in range(10):
        resultado = triage.ejecutar(Solicitud("GASES DEL ORINOCO", f"REQ-{numero}", TEXTO_JUANA))
        assert resultado.solicitud_tipo == "Incidente técnico"
    assert falso.llamados == 3


def _pedir_prioridad(proveedor: ProveedorConCortocircuito, empresa, veces: int) -> None:
    for _ in range(veces):
        with pytest.raises(ErrorProveedorPrioridad):
            proveedor.obtener(empresa, DOCUMENTO, "Retraso en entrega")


def test_proveedor_caido_abre_su_circuito_y_deja_de_llamarlo():
    falso, reloj = ProveedorPrioridadFalso(sin_respuesta=True), Reloj()
    proveedor = ProveedorConCortocircuito(falso, reloj)
    _pedir_prioridad(proveedor, MDV, 3)
    assert proveedor.circuito(MDV).abierto and len(falso.pedidos) == 3
    _pedir_prioridad(proveedor, MDV, 5)
    assert len(falso.pedidos) == 3
    reloj.ahora += 31
    falso.sin_respuesta = False
    assert proveedor.obtener(MDV, DOCUMENTO, "Retraso en entrega") is Prioridad.ALTA
    assert not proveedor.circuito(MDV).abierto


def test_n_y_x_salen_del_yaml_de_cada_empresa():
    corta = replace(
        MDV, proveedor_prioridad=replace(MDV.proveedor_prioridad, fallas_para_abrir=1, pausa_s=5)
    )
    otra = replace(MDV, nombre="OTRA EMPRESA")
    falso, reloj = ProveedorPrioridadFalso(sin_respuesta=True), Reloj()
    proveedor = ProveedorConCortocircuito(falso, reloj)
    _pedir_prioridad(proveedor, corta, 1)
    assert proveedor.circuito(corta).abierto
    # El circuito es por empresa: la caída de un cliente no corta a los demás.
    assert not proveedor.circuito(otra).abierto
    reloj.ahora += 6
    assert not proveedor.circuito(corta).abierto


def test_un_rechazo_no_cuenta_como_caida():
    falso = ProveedorPrioridadFalso(falla=True)
    proveedor = ProveedorConCortocircuito(falso, Reloj())
    _pedir_prioridad(proveedor, MDV, 5)
    assert not proveedor.circuito(MDV).abierto and len(falso.pedidos) == 5


def test_triage_con_proveedor_caido_usa_reglas_sin_llamarlo():
    falso = ProveedorPrioridadFalso(sin_respuesta=True)
    triage = CasoDeUsoTriage(
        CATALOGO,
        {nombre: PlataformaFalsa("EXT") for nombre in CATALOGO.nombres},
        None,
        proveedores_prioridad={"http": ProveedorConCortocircuito(falso, Reloj())},
        repositorio=RepositorioSolicitudesMemoria(),
    )
    for numero in range(6):
        resultado = triage.ejecutar(Solicitud("MENSAJERIA DEL VALLE", f"M-{numero}", TEXTO_MDV))
        assert "no se usó el servicio de prioridad del cliente" in resultado.justificacion
    assert len(falso.pedidos) == 3
    assert "se volverá a consultar" in resultado.justificacion
