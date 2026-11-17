from __future__ import annotations

import shutil

import pytest

from app.composicion import ErrorArranque, construir_triage
from services.configuracion_empresas import CARPETA_POR_DEFECTO


def test_arma_una_plataforma_por_empresa():
    triage = construir_triage()
    assert set(triage.plataformas) == set(triage.catalogo.nombres)


def test_plataforma_sin_adaptador_detiene_el_arranque(tmp_path):
    origen = CARPETA_POR_DEFECTO / "gases_del_orinoco.yaml"
    texto = origen.read_text(encoding="utf-8").replace("zendesk_simulada", "servicenow")
    (tmp_path / "gases.yaml").write_text(texto, encoding="utf-8")
    with pytest.raises(ErrorArranque, match="servicenow"):
        construir_triage(tmp_path)


def test_carpeta_sin_empresas_detiene_el_arranque(tmp_path):
    with pytest.raises(ErrorArranque):
        construir_triage(tmp_path)


def test_quinta_empresa_solo_con_su_yaml(tmp_path):
    for archivo in CARPETA_POR_DEFECTO.glob("*.yaml"):
        shutil.copy(archivo, tmp_path)
    texto = (CARPETA_POR_DEFECTO / "gases_del_orinoco.yaml").read_text(encoding="utf-8")
    texto = texto.replace("nombre: GASES DEL ORINOCO", "nombre: ACUEDUCTO DEL SUR")
    (tmp_path / "acueducto_del_sur.yaml").write_text(texto, encoding="utf-8")
    triage = construir_triage(tmp_path)
    assert "ACUEDUCTO DEL SUR" in triage.plataformas
