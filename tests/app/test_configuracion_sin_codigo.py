"""Tipos de documento y carpeta de empresas: se cambian por configuración, no en el código."""

from __future__ import annotations

import shutil

import pytest

from app.composicion import construir_triage
from app.triage import CasoDeUsoTriage
from domain.contrato import DocumentoCliente, Solicitud
from domain.documento_cliente import extraer_documento
from domain.puertos import AnalisisLLM
from services.analizador_llm import armar_instrucciones
from services.configuracion_empresas import (
    ARCHIVO_TIPOS_POR_DEFECTO,
    CARPETA_POR_DEFECTO,
    ConfiguracionInvalida,
    cargar_catalogo,
    cargar_tipos_documento,
)
from services.repositorio_memoria import RepositorioSolicitudesMemoria
from tests.app.falsos import AnalizadorFalso, PlataformaFalsa

PPT = (
    "  - codigo: PPT\n"
    "    nombre: permiso por protección temporal\n"
    "    etiqueta: 'permiso por proteccion temporal|\\bppt\\b'\n"
)
TEXTO_PPT = (
    "Desde ayer la estufa no prende y necesito que la revisen. Mi PPT es 4.567.890, gracias."
)


@pytest.fixture
def archivo_con_ppt(tmp_path):
    archivo = tmp_path / "tipos_documento.yaml"
    archivo.write_text(ARCHIVO_TIPOS_POR_DEFECTO.read_text(encoding="utf-8") + PPT, "utf-8")
    return archivo


def test_un_tipo_nuevo_se_reconoce_solo_con_configuracion(archivo_con_ppt):
    gases = cargar_catalogo(CARPETA_POR_DEFECTO, archivo_con_ppt).obtener("GASES DEL ORINOCO")
    assert extraer_documento(TEXTO_PPT, gases.tipos_documento) == DocumentoCliente("PPT", "4567890")
    assert "- PPT: permiso por protección temporal" in armar_instrucciones(gases)
    # Con la lista por defecto el mismo texto no trae documento.
    assert extraer_documento(TEXTO_PPT, cargar_tipos_documento()) is None


def test_el_documento_ppt_del_llm_se_acepta_y_llega_a_la_plataforma(archivo_con_ppt):
    catalogo = cargar_catalogo(CARPETA_POR_DEFECTO, archivo_con_ppt)
    plataformas = {nombre: PlataformaFalsa("EXT") for nombre in catalogo.nombres}
    analisis = AnalisisLLM(
        categoria="Incidente técnico",
        informacion_suficiente=True,
        hechos="la estufa no prende",
        tipo_documento="PPT",
        numero_documento="4567890",
    )
    triage = CasoDeUsoTriage(
        catalogo,
        plataformas,
        AnalizadorFalso(respuesta=analisis),
        repositorio=RepositorioSolicitudesMemoria(),
    )
    triage.ejecutar(Solicitud("GASES DEL ORINOCO", "PPT-1", TEXTO_PPT))
    assert plataformas["GASES DEL ORINOCO"].casos[0].documento == DocumentoCliente("PPT", "4567890")


def test_carpeta_empresas_por_variable_de_entorno(tmp_path, monkeypatch):
    shutil.copy(CARPETA_POR_DEFECTO / "gases_del_orinoco.yaml", tmp_path)
    monkeypatch.setenv("CARPETA_EMPRESAS", str(tmp_path))
    triage = construir_triage()
    assert triage.catalogo.nombres == ("GASES DEL ORINOCO",)


@pytest.mark.parametrize(
    ("extra", "culpable"),
    [
        ("  - codigo: CC\n    nombre: repetida\n    etiqueta: 'x'\n", "repetidos"),
        ("  - codigo: XX\n    nombre: mala\n    etiqueta: '(sin cerrar'\n", "etiqueta"),
    ],
)
def test_tipos_invalidos_detienen_el_arranque(tmp_path, extra, culpable):
    archivo = tmp_path / "tipos.yaml"
    archivo.write_text(ARCHIVO_TIPOS_POR_DEFECTO.read_text(encoding="utf-8") + extra, "utf-8")
    with pytest.raises(ConfiguracionInvalida, match=culpable):
        cargar_tipos_documento(archivo)
