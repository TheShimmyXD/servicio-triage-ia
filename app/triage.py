"""Caso de uso de triage: automatiza los pasos 1 a 6 del proceso para una solicitud.

Orden: empresa -> análisis (LLM validado o reglas) -> información mínima -> categoría ->
prioridad -> próximo paso -> justificación -> caso en la plataforma si es gestión externa.
Ninguna falla de un servicio de afuera tumba la respuesta: cada uno tiene su respaldo.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date

from domain.clasificacion import clasificar_por_palabras_clave
from domain.contrato import DocumentoCliente, ProximoPaso, ResultadoTriage, Solicitud
from domain.documento_cliente import extraer_documento
from domain.empresa import CatalogoEmpresas, ConfiguracionEmpresa
from domain.informacion_minima import evaluar_informacion_minima, extraer_hecho_principal
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
)

registro = logging.getLogger(__name__)

TIPOS_DOCUMENTO = frozenset({"CC", "CE", "NIT", "TI", "PA"})


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

    def ejecutar(self, solicitud: Solicitud) -> ResultadoTriage:
        # Lanza EmpresaNoParametrizada; la puerta la traduce a una respuesta clara.
        empresa = self.catalogo.obtener(solicitud.compania)
        texto = solicitud.solicitud_descripcion
        analisis = self._analizar_con_llm(texto, empresa, solicitud.solicitud_id)

        documento = _documento_verificado(analisis, texto)
        if analisis is not None:
            suficiente = analisis.informacion_suficiente
            categoria: str | None = analisis.categoria
            hecho = analisis.hechos or extraer_hecho_principal(texto)
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
            id_externo = self.plataformas[empresa.nombre].crear_caso(caso)

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
            estado=estado_para(paso),
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
            registro.warning("llm_fallo solicitud=%s motivo=%s", solicitud_id, error)
            return None
        if analisis.categoria not in empresa.nombres_categorias:
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
            registro.warning(
                "proveedor_prioridad_fallo empresa=%s motivo=%s", empresa.nombre, error
            )
            return DecisionPrioridad(
                por_reglas.prioridad,
                f"{por_reglas.motivo}; el servicio de prioridad del cliente no respondió",
            )
        return DecisionPrioridad(
            prioridad, "así lo indica el servicio de prioridad del cliente", "servicio del cliente"
        )


def _documento_verificado(analisis: AnalisisLLM | None, texto: str) -> DocumentoCliente | None:
    """Usa el documento del LLM solo si su número aparece en el texto; si no, las reglas.

    Evita que un número inventado por el modelo llegue a la plataforma del cliente.
    """
    if analisis and analisis.tipo_documento and analisis.numero_documento:
        tipo = analisis.tipo_documento.strip().upper()
        numero = re.sub(r"[^\dA-Za-z-]", "", analisis.numero_documento)
        digitos_texto = re.sub(r"\D", "", texto)
        digitos_numero = re.sub(r"\D", "", numero)
        if tipo in TIPOS_DOCUMENTO and len(digitos_numero) >= 5 and digitos_numero in digitos_texto:
            return DocumentoCliente(tipo, numero)
        registro.warning("llm_documento_no_verificado tipo=%s", tipo)
    return extraer_documento(texto)
