from __future__ import annotations

from domain.informacion_minima import (
    ElementoMinimo,
    evaluar_informacion_minima,
    extraer_hecho_principal,
)
from tests.domain.datos import TEXTO_INCOMPLETO, TEXTO_JUANA


def test_juana_tiene_los_tres_elementos():
    evaluacion = evaluar_informacion_minima(TEXTO_JUANA)
    assert evaluacion.suficiente
    assert evaluacion.encontrados == frozenset(ElementoMinimo)


def test_incompleta_le_faltan_que_paso_y_cuando():
    evaluacion = evaluar_informacion_minima(TEXTO_INCOMPLETO)
    assert not evaluacion.suficiente
    assert evaluacion.faltantes == {ElementoMinimo.QUE_PASO, ElementoMinimo.CUANDO}


def test_texto_muy_corto_es_insuficiente_aunque_tenga_marcador():
    assert not evaluar_informacion_minima("Hola, necesito ayuda").suficiente


def test_la_empresa_puede_exigir_menos_elementos():
    consulta = "¿Cuál es el horario de atención de las oficinas de Cali?"
    assert not evaluar_informacion_minima(consulta).suficiente
    relajada = evaluar_informacion_minima(consulta, requeridos={ElementoMinimo.QUE_NECESITA})
    assert relajada.suficiente


def test_marcadores_propios_de_la_empresa():
    texto = "Estoy sin señal en el celular desde el lunes, necesito que lo revisen"
    sin_extra = evaluar_informacion_minima(texto)
    assert ElementoMinimo.QUE_PASO not in sin_extra.encontrados
    con_extra = evaluar_informacion_minima(
        texto, marcadores_extra={ElementoMinimo.QUE_PASO: ["sin señal"]}
    )
    assert con_extra.suficiente


def test_hecho_principal_de_juana_sin_documento():
    hecho = extraer_hecho_principal(TEXTO_JUANA)
    assert hecho is not None
    assert hecho.startswith("la estufa")
    assert "presenta fallas" in hecho
    assert "102045678" not in hecho


def test_hecho_oculta_numeros_largos():
    hecho = extraer_hecho_principal("Con CC 102045678 tengo una fuga en el contador")
    assert hecho == "Con CC [documento] tengo una fuga en el contador"


def test_sin_hecho_devuelve_none():
    assert extraer_hecho_principal(TEXTO_INCOMPLETO) is None
