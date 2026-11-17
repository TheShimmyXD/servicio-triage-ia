from __future__ import annotations

from domain.contrato import EstadoCaso, ProximoPaso
from domain.proximo_paso import decidir_proximo_paso, estado_para
from tests.domain.datos import DELEGACIONES_GAS


def test_sin_informacion_se_cierra():
    paso = decidir_proximo_paso(False, "Incidente técnico", DELEGACIONES_GAS)
    assert paso is ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE


def test_sigue_la_delegacion_de_la_categoria():
    assert decidir_proximo_paso(True, "Incidente técnico", DELEGACIONES_GAS) is (
        ProximoPaso.GESTION_EXTERNA
    )
    assert decidir_proximo_paso(True, "Consulta", DELEGACIONES_GAS) is (
        ProximoPaso.RESPUESTA_DIRECTA
    )


def test_categoria_sin_delegacion_va_a_la_empresa():
    assert decidir_proximo_paso(True, "Nueva", DELEGACIONES_GAS) is ProximoPaso.GESTION_EXTERNA
    assert decidir_proximo_paso(True, None, DELEGACIONES_GAS) is ProximoPaso.GESTION_EXTERNA


def test_estado_segun_el_paso():
    assert estado_para(ProximoPaso.GESTION_EXTERNA) is EstadoCaso.PENDIENTE
    assert estado_para(ProximoPaso.RESPUESTA_DIRECTA) is EstadoCaso.CERRADO
    assert estado_para(ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE) is EstadoCaso.CERRADO
