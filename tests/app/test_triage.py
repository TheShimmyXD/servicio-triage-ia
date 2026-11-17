from __future__ import annotations

from datetime import date

import pytest

from app.triage import CasoDeUsoTriage
from domain.contrato import Prioridad, Solicitud
from domain.empresa import EmpresaNoParametrizada
from domain.puertos import AnalisisLLM
from services.configuracion_empresas import cargar_catalogo
from tests.app.falsos import AnalizadorFalso, PlataformaFalsa, ProveedorPrioridadFalso
from tests.domain.datos import TEXTO_INCOMPLETO, TEXTO_JUANA

HOY = date(2026, 11, 17)
REQ_001 = Solicitud("GASES DEL ORINOCO", "REQ-001", TEXTO_JUANA)
TEXTO_MDV = (
    "Mi paquete no ha llegado y ya pasó una semana desde la fecha prometida, necesito "
    "saber qué pasó. Mi cédula es 1144556677"
)


def _armar(analizador=None, proveedor=None):
    catalogo = cargar_catalogo()
    plataformas = {nombre: PlataformaFalsa(prefijo="EXT") for nombre in catalogo.nombres}
    caso_de_uso = CasoDeUsoTriage(
        catalogo=catalogo,
        plataformas=plataformas,
        analizador=analizador,
        proveedores_prioridad={"http": proveedor} if proveedor else None,
        hoy=lambda: HOY,
    )
    return caso_de_uso, plataformas


def _assert_juana(resultado):
    assert resultado.solicitud_tipo == "Incidente técnico"
    assert resultado.solicitud_prioridad is Prioridad.ALTA
    assert resultado.proximo_paso.value == "GESTION_EXTERNA"
    assert resultado.solicitud_tipo_id_cliente == "CC"
    assert resultado.solicitud_id_cliente == "102045678"
    assert resultado.estado.value == "pendiente"
    assert resultado.solicitud_fecha == HOY


def test_req_001_por_reglas_crea_el_caso_externo():
    caso_de_uso, plataformas = _armar()
    resultado = caso_de_uso.ejecutar(REQ_001)
    _assert_juana(resultado)
    casos = plataformas["GASES DEL ORINOCO"].casos
    assert len(casos) == 1
    assert resultado.solicitud_id_plataforma_externa == "EXT-000001"
    assert casos[0].prioridad is Prioridad.ALTA
    assert "estufa" in resultado.justificacion


def test_req_001_con_llm_valido():
    analisis = AnalisisLLM(
        categoria="Incidente técnico",
        informacion_suficiente=True,
        hechos="estufa comprada hace 2 semanas no hace contacto con la llave del gas",
        tipo_documento="CC",
        numero_documento="102045678",
    )
    caso_de_uso, _ = _armar(AnalizadorFalso(respuesta=analisis))
    resultado = caso_de_uso.ejecutar(REQ_001)
    _assert_juana(resultado)
    assert "no hace contacto con la llave del gas" in resultado.justificacion


def test_si_el_llm_falla_se_usa_el_respaldo(caplog):
    analizador = AnalizadorFalso(error="timeout de 10 s")
    caso_de_uso, _ = _armar(analizador)
    resultado = caso_de_uso.ejecutar(REQ_001)
    _assert_juana(resultado)
    assert analizador.llamados == 1
    assert "llm_fallo" in caplog.text


def test_categoria_ajena_del_llm_se_descarta():
    analisis = AnalisisLLM(categoria="Hackeo", informacion_suficiente=True)
    caso_de_uso, _ = _armar(AnalizadorFalso(respuesta=analisis))
    _assert_juana(caso_de_uso.ejecutar(REQ_001))


def test_documento_inventado_por_el_llm_se_reemplaza_por_el_del_texto():
    analisis = AnalisisLLM(
        categoria="Incidente técnico",
        informacion_suficiente=True,
        tipo_documento="CC",
        numero_documento="999999999",
    )
    caso_de_uso, _ = _armar(AnalizadorFalso(respuesta=analisis))
    assert caso_de_uso.ejecutar(REQ_001).solicitud_id_cliente == "102045678"


def test_solicitud_incompleta_se_cierra_sin_crear_caso():
    caso_de_uso, plataformas = _armar()
    resultado = caso_de_uso.ejecutar(Solicitud("GASES DEL ORINOCO", "REQ-002", TEXTO_INCOMPLETO))
    assert resultado.proximo_paso.value == "CIERRE_POR_INFORMACION_INSUFICIENTE"
    assert resultado.justificacion == "Información incompleta o faltante"
    assert resultado.estado.value == "cerrado"
    assert resultado.solicitud_prioridad is None
    assert resultado.solicitud_id_plataforma_externa is None
    assert not plataformas["GASES DEL ORINOCO"].casos


def test_respuesta_directa_cierra_sin_plataforma():
    caso_de_uso, plataformas = _armar()
    texto = "Necesito agendar una cita con el especialista porque me duele la rodilla"
    resultado = caso_de_uso.ejecutar(Solicitud("Salud Integral del Llano", "S-1", texto))
    assert resultado.solicitud_tipo == "Cita médica"
    assert resultado.proximo_paso.value == "RESPUESTA_DIRECTA"
    assert resultado.estado.value == "cerrado"
    assert resultado.solicitud_prioridad is Prioridad.BAJA
    assert not plataformas["SALUD INTEGRAL DEL LLANO"].casos


def test_empresa_no_parametrizada():
    caso_de_uso, _ = _armar()
    with pytest.raises(EmpresaNoParametrizada):
        caso_de_uso.ejecutar(Solicitud("ACUEDUCTO DEL SUR", "X-1", TEXTO_JUANA))


def test_mensajeria_del_valle_usa_el_servicio_del_cliente():
    proveedor = ProveedorPrioridadFalso(prioridad=Prioridad.ALTA)
    caso_de_uso, _ = _armar(proveedor=proveedor)
    resultado = caso_de_uso.ejecutar(Solicitud("MENSAJERIA DEL VALLE", "M-1", TEXTO_MDV))
    assert resultado.solicitud_tipo == "Envío retrasado"
    assert resultado.solicitud_prioridad is Prioridad.ALTA
    assert "servicio del cliente" in resultado.justificacion
    documento, categoria = proveedor.pedidos[0]
    assert (documento.tipo, documento.numero, categoria) == ("CC", "1144556677", "Envío retrasado")


def test_si_el_servicio_del_cliente_falla_se_usan_las_reglas():
    caso_de_uso, _ = _armar(proveedor=ProveedorPrioridadFalso(falla=True))
    resultado = caso_de_uso.ejecutar(Solicitud("MENSAJERIA DEL VALLE", "M-2", TEXTO_MDV))
    assert resultado.solicitud_prioridad is Prioridad.MEDIA
    assert "no respondió" in resultado.justificacion
    assert "reglas de la empresa" in resultado.justificacion
