from __future__ import annotations

import pytest

from app.cortocircuito import AnalizadorConCortocircuito
from app.triage import CasoDeUsoTriage
from domain.contrato import Solicitud
from domain.puertos import AnalisisLLM, ErrorLLM
from services.configuracion_empresas import cargar_catalogo
from services.repositorio_memoria import RepositorioSolicitudesMemoria
from tests.app.falsos import AnalizadorFalso, PlataformaFalsa
from tests.domain.datos import TEXTO_JUANA

CATALOGO = cargar_catalogo()
GAS = CATALOGO.obtener("GASES DEL ORINOCO")
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
