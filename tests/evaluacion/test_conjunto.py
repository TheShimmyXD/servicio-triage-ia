from __future__ import annotations

from collections import Counter

from domain.contrato import ProximoPaso
from evaluacion.medir_exactitud import cargar_conjunto, medir
from services.ajustes import AjustesLLM
from services.configuracion_empresas import cargar_catalogo

CONJUNTO = cargar_conjunto()
CATALOGO = cargar_catalogo()


def test_conjunto_cubre_las_cuatro_empresas_con_ids_unicos():
    assert len(CONJUNTO) >= 30
    assert len({caso.id for caso in CONJUNTO}) == len(CONJUNTO)
    por_empresa = Counter(caso.compania for caso in CONJUNTO)
    assert set(por_empresa) == set(CATALOGO.nombres)
    # Cada empresa trae casos sin la información mínima.
    for nombre in CATALOGO.nombres:
        assert any(c.compania == nombre and not c.suficiente for c in CONJUNTO)


def test_etiquetas_coinciden_con_la_configuracion_de_cada_empresa():
    # Si un YAML cambia de categorías o delegaciones, el conjunto debe revisarse.
    for caso in CONJUNTO:
        empresa = CATALOGO.obtener(caso.compania)
        if caso.categoria is None:
            assert caso.proximo_paso is ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE
        else:
            assert caso.categoria in empresa.nombres_categorias, caso.id
            assert caso.proximo_paso is empresa.delegaciones[caso.categoria], caso.id


def test_modo_reglas_mide_todo_el_conjunto_sin_red():
    medicion = medir(CONJUNTO, AjustesLLM(llm_proveedor="ninguno"), "reglas")
    assert medicion.total == len(CONJUNTO)
    assert medicion.con_categoria == sum(c.categoria is not None for c in CONJUNTO)
    assert medicion.respaldos == 0
