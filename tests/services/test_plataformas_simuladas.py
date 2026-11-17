from __future__ import annotations

import pytest

from domain.empresa import ConfiguracionPlataforma
from domain.puertos import CasoExterno
from services.plataformas_simuladas import PlataformaDesconocida, crear_plataforma

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
