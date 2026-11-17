"""Caso de uso de triage: automatiza los pasos 1 a 6 del proceso para una solicitud.

Orden: empresa -> duplicados -> análisis (LLM validado o reglas) -> información mínima ->
categoría -> prioridad -> próximo paso -> justificación -> caso en la plataforma si es
gestión externa. Ninguna falla de un servicio de afuera tumba la respuesta: cada uno
tiene su respaldo, y la plataforma caída deja el estado y el motivo en la respuesta.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from app.metricas import Evento, Metricas
from app.reintentos import PoliticaReintentos, crear_con_reintentos
from domain.clasificacion import clasificar_por_palabras_clave
from domain.contrato import (
    DocumentoCliente,
    EstadoCaso,
    ProximoPaso,
    ResultadoTriage,
    Solicitud,
)
from domain.documento_cliente import TiposDocumento, extraer_documento
from domain.duplicados import (
    AccionAnteDuplicado,
    SolicitudAtendida,
    SolicitudEnConflicto,
    decidir_ante_duplicado,
    normalizar_texto,
)
from domain.empresa import CatalogoEmpresas, ConfiguracionEmpresa
from domain.informacion_minima import (
    evaluar_informacion_minima,
    extraer_hecho_principal,
    hecho_fiel_al_texto,
)
from domain.justificacion import construir_justificacion
from domain.prioridad import DecisionPrioridad, calcular_prioridad
from domain.proximo_paso import decidir_proximo_paso, estado_para
from domain.puertos import (
    AnalisisLLM,
    AnalizadorLLM,
    CasoExterno,
    ErrorLLM,
    ErrorProveedorPrioridad,
    PlataformaCasos,
    ProveedorPrioridad,
    RepositorioSolicitudes,
)

registro = logging.getLogger(__name__)


@dataclass
class _CandadoCompartido:
    candado: threading.Lock = field(default_factory=threading.Lock)
    usuarios: int = 0
    """Solicitudes con esta clave que esperan o tienen el candado."""


@dataclass
class CasoDeUsoTriage:
    """Se arma una vez al arrancar (app/composicion) y atiende todas las solicitudes."""

    catalogo: CatalogoEmpresas
    plataformas: Mapping[str, PlataformaCasos]
    """Plataforma de cada empresa, por el nombre de la empresa tal como está en su YAML."""
    analizador: AnalizadorLLM | None = None
    proveedores_prioridad: Mapping[str, ProveedorPrioridad] | None = None
    """Proveedores externos por tipo ("http"). El tipo "reglas" no necesita proveedor."""
    hoy: Callable[[], date] = date.today
    repositorio: RepositorioSolicitudes = field(kw_only=True)
    """Lo entrega app/composicion: el caso de uso solo conoce el puerto del dominio."""
    metricas: Metricas = field(default_factory=Metricas)
    dormir: Callable[[float], None] = time.sleep
    """Las pruebas lo reemplazan para no esperar los reintentos."""
    _candados: dict[tuple[str, str], _CandadoCompartido] = field(default_factory=dict, init=False)
    """Solo las claves en curso: cada candado se borra cuando nadie lo usa."""
    _candado_general: threading.Lock = field(default_factory=threading.Lock, init=False)

    def ejecutar(self, solicitud: Solicitud) -> ResultadoTriage:
        # Lanza EmpresaNoParametrizada; la puerta la traduce a una respuesta clara.
        empresa = self.catalogo.obtener(solicitud.compania)
        clave = (empresa.nombre, solicitud.solicitud_id)
        # Dos envíos simultáneos de la misma solicitud no deben crear dos casos.
        with self._exclusivo(clave):
            previa = self.repositorio.obtener(*clave)
            accion = decidir_ante_duplicado(previa, solicitud.solicitud_descripcion)
            if accion is AccionAnteDuplicado.CONFLICTO:
                self.metricas.sumar(Evento.CONFLICTO, empresa.nombre)
                registro.warning("solicitud_en_conflicto empresa=%s solicitud=%s", *clave)
                raise SolicitudEnConflicto(*clave)
            if accion is AccionAnteDuplicado.DEVOLVER_EXISTENTE and previa is not None:
                self.metricas.sumar(Evento.DUPLICADO_DEVUELTO, empresa.nombre)
                registro.info("solicitud_duplicada empresa=%s solicitud=%s", *clave)
                return previa.resultado
            resultado = self._triar(empresa, solicitud)
            texto = normalizar_texto(solicitud.solicitud_descripcion)
            self.repositorio.guardar(*clave, SolicitudAtendida(texto, resultado))
            return resultado

    @contextmanager
    def _exclusivo(self, clave: tuple[str, str]) -> Iterator[None]:
        with self._candado_general:
            compartido = self._candados.setdefault(clave, _CandadoCompartido())
            compartido.usuarios += 1
        try:
            with compartido.candado:
                yield
        finally:
            # Sin esto el diccionario crecería con cada solicitud atendida.
            with self._candado_general:
                compartido.usuarios -= 1
                if compartido.usuarios == 0:
                    del self._candados[clave]

    def _triar(self, empresa: ConfiguracionEmpresa, solicitud: Solicitud) -> ResultadoTriage:
        texto = solicitud.solicitud_descripcion
        analisis = self._analizar_con_llm(texto, empresa, solicitud.solicitud_id)

        documento = _documento_verificado(analisis, texto, empresa.tipos_documento)
        if analisis is not None:
            suficiente = analisis.informacion_suficiente
            # El esquema obliga al LLM a elegir una categoría aun sin datos; si dice que la
            # información no alcanza, la categoría solo se conserva si las reglas la ven.
            categoria: str | None = (
                analisis.categoria
                if suficiente
                else clasificar_por_palabras_clave(texto, empresa.categorias)
            )
            hecho = _hecho_verificado(analisis, texto, solicitud.solicitud_id)
        else:
            reglas_info = empresa.informacion_minima
            suficiente = evaluar_informacion_minima(
                texto, reglas_info.requeridos, reglas_info.frases_extra
            ).suficiente
            categoria = clasificar_por_palabras_clave(texto, empresa.categorias)
            hecho = extraer_hecho_principal(texto)

        paso = decidir_proximo_paso(suficiente, categoria, empresa.delegaciones)
        decision = self._priorizar(empresa, categoria, documento, texto) if suficiente else None
        justificacion = construir_justificacion(paso, categoria, decision, hecho)

        id_externo = None
        estado = estado_para(paso)
        if paso is ProximoPaso.GESTION_EXTERNA:
            caso = CasoExterno(
                compania=empresa.nombre,
                solicitud_id=solicitud.solicitud_id,
                categoria=categoria,
                prioridad=decision.prioridad if decision else None,
                documento=documento,
                descripcion=texto,
                justificacion=justificacion,
            )
            nombre_plataforma = empresa.plataforma.nombre
            creacion = crear_con_reintentos(
                self.plataformas[empresa.nombre],
                caso,
                nombre_plataforma,
                PoliticaReintentos(
                    intentos=empresa.plataforma.intentos,
                    espera_inicial=empresa.plataforma.espera_inicial_s,
                ),
                self.metricas,
                self.dormir,
            )
            id_externo = creacion.id_externo
            if id_externo is None:
                estado = EstadoCaso.ERROR_PLATAFORMA
                justificacion = (
                    f"{justificacion} No se pudo crear el caso en {nombre_plataforma} tras "
                    f"{creacion.intentos} {'intento' if creacion.intentos == 1 else 'intentos'} "
                    f"({creacion.motivo}); reenviar la misma "
                    "solicitud lo vuelve a intentar."
                )

        registro.info(
            "triage empresa=%s solicitud=%s fuente=%s categoria=%s paso=%s",
            empresa.nombre,
            solicitud.solicitud_id,
            "llm" if analisis else "reglas",
            categoria,
            paso.value,
        )
        return ResultadoTriage(
            compania=empresa.nombre,
            solicitud_id=solicitud.solicitud_id,
            solicitud_fecha=self.hoy(),
            solicitud_tipo=categoria,
            solicitud_prioridad=decision.prioridad if decision else None,
            solicitud_tipo_id_cliente=documento.tipo if documento else None,
            solicitud_id_cliente=documento.numero if documento else None,
            solicitud_id_plataforma_externa=id_externo,
            proximo_paso=paso,
            justificacion=justificacion,
            estado=estado,
        )

    def _analizar_con_llm(
        self, texto: str, empresa: ConfiguracionEmpresa, solicitud_id: str
    ) -> AnalisisLLM | None:
        """Pide el análisis al LLM y lo descarta si falla o nombra una categoría ajena."""
        if self.analizador is None:
            return None
        try:
            analisis = self.analizador.analizar(texto, empresa)
        except ErrorLLM as error:
            self.metricas.sumar(Evento.LLM_FALLIDO, empresa.nombre)
            registro.warning("llm_fallo solicitud=%s motivo=%s", solicitud_id, error)
            return None
        if analisis.categoria not in empresa.nombres_categorias:
            self.metricas.sumar(Evento.LLM_FALLIDO, empresa.nombre)
            # El esquema ya limita la categoría; esta revisión cubre proveedores sin esquema.
            registro.warning(
                "llm_categoria_invalida solicitud=%s categoria=%r", solicitud_id, analisis.categoria
            )
            return None
        return analisis

    def _priorizar(
        self,
        empresa: ConfiguracionEmpresa,
        categoria: str | None,
        documento: DocumentoCliente | None,
        texto: str,
    ) -> DecisionPrioridad:
        """Reglas de la empresa o, si tiene uno, su servicio externo con las reglas de respaldo."""
        por_reglas = calcular_prioridad(categoria, texto, empresa.reglas_prioridad)
        tipo = empresa.proveedor_prioridad.tipo
        if tipo == "reglas":
            return por_reglas
        proveedor = (self.proveedores_prioridad or {}).get(tipo)
        if proveedor is None:
            registro.warning("proveedor_prioridad_ausente empresa=%s tipo=%s", empresa.nombre, tipo)
            return por_reglas
        try:
            prioridad = proveedor.obtener(empresa, documento, categoria)
        except ErrorProveedorPrioridad as error:
            self.metricas.sumar(Evento.PRIORIDAD_EXTERNA_FALLIDA, empresa.nombre)
            registro.warning(
                "proveedor_prioridad_fallo empresa=%s motivo=%s", empresa.nombre, error
            )
            return DecisionPrioridad(
                por_reglas.prioridad,
                f"{por_reglas.motivo}; no se usó el servicio de prioridad del cliente ({error})",
            )
        return DecisionPrioridad(
            prioridad, "así lo indica el servicio de prioridad del cliente", "servicio del cliente"
        )


def _hecho_verificado(analisis: AnalisisLLM, texto: str, solicitud_id: str) -> str | None:
    """Cita el hecho del LLM solo si sale del texto; si no, el de las reglas.

    La justificación lo pone entre comillas y llega a la plataforma del cliente: una
    paráfrasis o un texto inyectado no pueden pasar por palabras del cliente.
    """
    hecho = hecho_fiel_al_texto(analisis.hechos, texto)
    if hecho is None and analisis.hechos:
        registro.warning("llm_hecho_no_verificado solicitud=%s", solicitud_id)
    return hecho or extraer_hecho_principal(texto)


def _documento_verificado(
    analisis: AnalisisLLM | None, texto: str, tipos: TiposDocumento
) -> DocumentoCliente | None:
    """Usa el documento del LLM solo si su número aparece en el texto; si no, las reglas.

    Evita que un número inventado por el modelo llegue a la plataforma del cliente.
    """
    if analisis and analisis.tipo_documento and analisis.numero_documento:
        tipo = analisis.tipo_documento.strip().upper()
        numero = re.sub(r"[^\dA-Za-z-]", "", analisis.numero_documento)
        digitos_texto = re.sub(r"\D", "", texto)
        digitos_numero = re.sub(r"\D", "", numero)
        if tipo in tipos.codigos and len(digitos_numero) >= 5 and digitos_numero in digitos_texto:
            return DocumentoCliente(tipo, numero)
        registro.warning("llm_documento_no_verificado tipo=%s", tipo)
    return extraer_documento(texto, tipos)
