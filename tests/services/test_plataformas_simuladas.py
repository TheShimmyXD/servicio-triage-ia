from __future__ import annotations

import pytest

from domain.duplicados import SolicitudAtendida
from domain.empresa import ConfiguracionPlataforma
from domain.puertos import CasoExterno, ErrorPlataforma
from services.plataformas_simuladas import (
    ParametrosPlataformaInvalidos,
    PlataformaDesconocida,
    crear_plataforma,
)
from services.repositorio_memoria import RepositorioSolicitudesMemoria

CASO = CasoExterno("GASES DEL ORINOCO", "REQ-001", None, None, None, "texto", "motivo")


def test_id_ficticio_con_el_prefijo_del_yaml():
    plataforma = crear_plataforma(ConfiguracionPlataforma("zendesk_simulada", {"prefijo": "zd"}))
    assert plataforma.crear_caso(CASO) == "ZD-000001"
    assert plataforma.crear_caso(CASO) == "ZD-000002"


def test_plataforma_simulada_nueva_solo_con_el_yaml():
    plataforma = crear_plataforma(ConfiguracionPlataforma("hubspot_simulada"))
    assert plataforma.crear_caso(CASO) == "HUBSPOT-000001"


def test_plataforma_sin_adaptador_se_rechaza():
    with pytest.raises(PlataformaDesconocida, match="servicenow"):
        crear_plataforma(ConfiguracionPlataforma("servicenow"))


def test_fallas_iniciales_desde_el_yaml():
    configuracion = ConfiguracionPlataforma("zendesk_simulada", {"fallas_iniciales": 2})
    plataforma = crear_plataforma(configuracion)
    for _ in range(2):
        with pytest.raises(ErrorPlataforma, match="falla simulada"):
            plataforma.crear_caso(CASO)
    assert plataforma.crear_caso(CASO) == "ZENDESK-000001"


def test_probabilidad_de_falla_total():
    configuracion = ConfiguracionPlataforma("zendesk_simulada", {"probabilidad_falla": 1})
    with pytest.raises(ErrorPlataforma):
        crear_plataforma(configuracion).crear_caso(CASO)


@pytest.mark.parametrize(
    "parametros",
    [{"fallas_iniciales": -1}, {"probabilidad_falla": 1.5}, {"fallas_iniciales": "muchas"}],
)
def test_parametros_de_falla_invalidos(parametros):
    with pytest.raises(ParametrosPlataformaInvalidos):
        crear_plataforma(ConfiguracionPlataforma("zendesk_simulada", parametros))


def test_repositorio_guarda_por_empresa_y_id():
    repositorio = RepositorioSolicitudesMemoria()
    atendida = SolicitudAtendida("texto", None)  # type: ignore[arg-type]
    repositorio.guardar("GASES DEL ORINOCO", "REQ-001", atendida)
    assert repositorio.obtener("GASES DEL ORINOCO", "REQ-001") is atendida
    assert repositorio.obtener("RED MOVIL ANDINA", "REQ-001") is None
