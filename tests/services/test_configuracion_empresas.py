from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from domain.contrato import Prioridad, ProximoPaso
from domain.empresa import EmpresaNoParametrizada
from domain.informacion_minima import ElementoMinimo, evaluar_informacion_minima
from domain.prioridad import calcular_prioridad
from domain.proximo_paso import decidir_proximo_paso
from services.configuracion_empresas import (
    CARPETA_POR_DEFECTO,
    ConfiguracionInvalida,
    cargar_catalogo,
    cargar_empresa,
)

EMPRESAS_ESPERADAS = (
    "GASES DEL ORINOCO",
    "MENSAJERIA DEL VALLE",
    "RED MOVIL ANDINA",
    "SALUD INTEGRAL DEL LLANO",
)

EMPRESA_MINIMA = """\
nombre: {nombre}
categorias:
  - nombre: Falla
    descripcion: Algo dejó de funcionar.
    palabras_clave: [falla]
reglas_prioridad:
  por_defecto: Baja
  por_categoria: {{Falla: Media}}
  senales:
    - prioridad: Alta
      frases: [urgente]
delegaciones:
  Falla: GESTION_EXTERNA
plataforma:
  nombre: zendesk_simulada
"""


def _escribir(carpeta: Path, nombre_archivo: str, contenido: str) -> Path:
    archivo = carpeta / nombre_archivo
    archivo.write_text(contenido, encoding="utf-8")
    return archivo


def test_carga_las_cuatro_empresas():
    catalogo = cargar_catalogo()
    assert catalogo.nombres == EMPRESAS_ESPERADAS


def test_cada_categoria_tiene_delegacion_y_prioridad():
    for empresa in (cargar_catalogo().obtener(n) for n in EMPRESAS_ESPERADAS):
        assert set(empresa.delegaciones) == set(empresa.nombres_categorias)
        assert set(empresa.reglas_prioridad.por_categoria) <= set(empresa.nombres_categorias)


def test_el_nombre_se_normaliza():
    catalogo = cargar_catalogo()
    assert catalogo.obtener("  gases del  orinóco ").nombre == "GASES DEL ORINOCO"


def test_empresa_no_parametrizada_da_codigo_y_lista_de_validas():
    with pytest.raises(EmpresaNoParametrizada) as error:
        cargar_catalogo().obtener("ACUEDUCTO DEL SUR")
    assert error.value.codigo == "EMPRESA_NO_PARAMETRIZADA"
    assert error.value.validas == EMPRESAS_ESPERADAS


def test_mensajeria_del_valle_usa_su_servicio_de_prioridad():
    mdv = cargar_catalogo().obtener("MENSAJERIA DEL VALLE")
    assert mdv.proveedor_prioridad.tipo == "http"
    assert mdv.proveedor_prioridad.url == "http://127.0.0.1:8001/prioridad"
    assert mdv.proveedor_prioridad.reintentos == 2
    assert mdv.proveedor_prioridad.fallas_para_abrir == 3
    assert mdv.proveedor_prioridad.pausa_s == 30
    gases = cargar_catalogo().obtener("GASES DEL ORINOCO")
    assert gases.proveedor_prioridad.tipo == "reglas"


def test_cada_empresa_tiene_su_plataforma():
    catalogo = cargar_catalogo()
    plataformas = {catalogo.obtener(n).plataforma.nombre for n in EMPRESAS_ESPERADAS}
    assert len(plataformas) == 4


def test_salud_exige_menos_elementos():
    salud = cargar_catalogo().obtener("SALUD INTEGRAL DEL LLANO")
    assert salud.informacion_minima.requeridos == {
        ElementoMinimo.QUE_PASO,
        ElementoMinimo.QUE_NECESITA,
    }


@pytest.mark.parametrize(
    "texto",
    [
        "Mi hijo tiene fiebre alta desde anoche, necesito que lo atiendan hoy",
        "Mi mamá tiene la fiebre muy alta y no baja",
        "Necesito una cita, que me atiendan hoy por favor",
        "Mi papá convulsionó en la casa, pido cita con neurología",
    ],
)
def test_salud_sube_a_alta_por_sintoma_o_atencion_del_dia(texto):
    salud = cargar_catalogo().obtener("SALUD INTEGRAL DEL LLANO")
    decision = calcular_prioridad("Cita médica", texto, salud.reglas_prioridad)
    assert decision.prioridad is Prioridad.ALTA


def test_salud_cita_de_rutina_sigue_en_baja():
    salud = cargar_catalogo().obtener("SALUD INTEGRAL DEL LLANO")
    texto = "Quiero agendar una cita de medicina general para el próximo mes, hoy no puedo ir"
    decision = calcular_prioridad("Cita médica", texto, salud.reglas_prioridad)
    assert decision.prioridad is Prioridad.BAJA


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        (("  Falla: GESTION_EXTERNA\n", "  Otra: GESTION_EXTERNA\n"), "categorías sin delegación"),
        (("  Falla: GESTION_EXTERNA\n", "  Falla: TALVEZ\n"), "delegaciones.Falla"),
        (("por_defecto: Baja", "por_defecto: Urgentisima"), "por_defecto"),
        (("plataforma:", "plataformas:"), "plataformas"),
        (("{Falla: Media}", "{Otra: Media}"), "categorías que no existen"),
        (("palabras_clave: [falla]", "palabras_clave: []"), "palabras_clave"),
        (
            ("  nombre: zendesk_simulada\n", "  nombre: zendesk_simulada\n  intentos: 0\n"),
            "intentos",
        ),
    ],
)
def test_rechaza_una_empresa_mal_formada(tmp_path, cambio, mensaje):
    viejo, nuevo = cambio
    contenido = EMPRESA_MINIMA.format(nombre="MALA")
    assert viejo in contenido
    archivo = _escribir(tmp_path, "mala.yaml", contenido.replace(viejo, nuevo))
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_empresa(archivo)
    assert "mala.yaml" in str(error.value)
    assert mensaje in str(error.value)


def test_rechaza_yaml_roto(tmp_path):
    archivo = _escribir(tmp_path, "rota.yaml", "nombre: [sin cerrar\n")
    with pytest.raises(ConfiguracionInvalida, match="YAML mal formado"):
        cargar_empresa(archivo)


def test_proveedor_http_exige_url(tmp_path):
    contenido = EMPRESA_MINIMA.format(nombre="HTTP") + "proveedor_prioridad:\n  tipo: http\n"
    with pytest.raises(ConfiguracionInvalida, match="url"):
        cargar_empresa(_escribir(tmp_path, "http.yaml", contenido))


def test_cortocircuito_del_proveedor_por_defecto_y_rango(tmp_path):
    base = EMPRESA_MINIMA.format(nombre="HTTP") + (
        "proveedor_prioridad:\n  tipo: http\n  url: http://cliente/prioridad\n"
    )
    proveedor = cargar_empresa(_escribir(tmp_path, "a.yaml", base)).proveedor_prioridad
    assert (proveedor.fallas_para_abrir, proveedor.pausa_s) == (3, 30.0)
    with pytest.raises(ConfiguracionInvalida, match="fallas_para_abrir"):
        cargar_empresa(_escribir(tmp_path, "b.yaml", base + "  fallas_para_abrir: 0\n"))


def test_rechaza_empresa_repetida_y_carpeta_vacia(tmp_path):
    with pytest.raises(ConfiguracionInvalida, match="No hay archivos"):
        cargar_catalogo(tmp_path)
    _escribir(tmp_path, "a.yaml", EMPRESA_MINIMA.format(nombre="REPETIDA"))
    _escribir(tmp_path, "b.yaml", EMPRESA_MINIMA.format(nombre="repetida"))
    with pytest.raises(ConfiguracionInvalida, match="repetida"):
        cargar_catalogo(tmp_path)


def test_quinta_empresa_solo_con_un_archivo(tmp_path):
    """Agregar una empresa no toca el código: se copia la carpeta y se suma un YAML."""
    for archivo in CARPETA_POR_DEFECTO.glob("*.yaml"):
        shutil.copy(archivo, tmp_path)
    _escribir(tmp_path, "acueducto_del_sur.yaml", EMPRESA_MINIMA.format(nombre="ACUEDUCTO DEL SUR"))

    catalogo = cargar_catalogo(tmp_path)
    assert len(catalogo) == 5
    nueva = catalogo.obtener("Acueducto del Sur")

    texto = "Desde ayer hay una falla urgente en el contador y necesito que la revisen"
    evaluacion = evaluar_informacion_minima(
        texto, nueva.informacion_minima.requeridos, nueva.informacion_minima.frases_extra
    )
    assert evaluacion.suficiente
    assert calcular_prioridad("Falla", texto, nueva.reglas_prioridad).prioridad is Prioridad.ALTA
    assert decidir_proximo_paso(True, "Falla", nueva.delegaciones) is ProximoPaso.GESTION_EXTERNA


def test_reintentos_de_plataforma_por_empresa(tmp_path):
    contenido = EMPRESA_MINIMA.format(nombre="UNA").replace(
        "  nombre: zendesk_simulada\n",
        "  nombre: zendesk_simulada\n  intentos: 1\n  espera_inicial_s: 0\n",
    )
    empresa = cargar_empresa(_escribir(tmp_path, "una.yaml", contenido))
    assert (empresa.plataforma.intentos, empresa.plataforma.espera_inicial_s) == (1, 0)
    # Sin los campos, los valores de siempre.
    por_defecto = cargar_empresa(_escribir(tmp_path, "dos.yaml", EMPRESA_MINIMA.format(nombre="D")))
    assert (por_defecto.plataforma.intentos, por_defecto.plataforma.espera_inicial_s) == (3, 0.2)


def test_informacion_minima_por_categoria(tmp_path):
    base = EMPRESA_MINIMA.format(nombre="CAT")
    reglas = cargar_empresa(_escribir(tmp_path, "a.yaml", base)).informacion_minima
    assert reglas.requeridos_para("Falla") == frozenset(ElementoMinimo)

    con_excepcion = base + "informacion_minima:\n  por_categoria:\n    Falla: [que_necesita]\n"
    reglas = cargar_empresa(_escribir(tmp_path, "b.yaml", con_excepcion)).informacion_minima
    assert reglas.requeridos_para("Falla") == {ElementoMinimo.QUE_NECESITA}
    assert reglas.requeridos_para(None) == frozenset(ElementoMinimo)


@pytest.mark.parametrize(
    ("bloque", "mensaje"),
    [
        ("    Otra: [que_necesita]\n", "por_categoria nombra categorías que no existen"),
        ("    Falla: []\n", "por_categoria"),
    ],
)
def test_rechaza_informacion_minima_por_categoria_mal_formada(tmp_path, bloque, mensaje):
    contenido = EMPRESA_MINIMA.format(nombre="MALA") + (
        "informacion_minima:\n  por_categoria:\n" + bloque
    )
    with pytest.raises(ConfiguracionInvalida, match=mensaje):
        cargar_empresa(_escribir(tmp_path, "mala.yaml", contenido))
