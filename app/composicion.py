"""Raíz de composición: lee la configuración y arma el caso de uso con sus servicios.

Se ejecuta una vez al arrancar. Si la configuración no sirve, el servicio no arranca y
dice por qué: es mejor que responder con una empresa a medio configurar.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.triage import CasoDeUsoTriage
from services.ajustes import AjustesLLM, AjustesProveedores
from services.analizador_llm import crear_analizador
from services.configuracion_empresas import (
    CARPETA_POR_DEFECTO,
    ConfiguracionInvalida,
    cargar_catalogo,
)
from services.plataformas_simuladas import (
    ParametrosPlataformaInvalidos,
    PlataformaDesconocida,
    crear_plataforma,
)
from services.proveedor_prioridad_http import ProveedorPrioridadHTTP

registro = logging.getLogger(__name__)


class ErrorArranque(RuntimeError):
    """Configuración de empresas o de plataformas que no permite arrancar."""


def construir_triage(
    carpeta_empresas: Path | None = None,
    ajustes_llm: AjustesLLM | None = None,
    ajustes_proveedores: AjustesProveedores | None = None,
) -> CasoDeUsoTriage:
    carpeta = carpeta_empresas or CARPETA_POR_DEFECTO
    try:
        catalogo = cargar_catalogo(carpeta)
        plataformas = {e.nombre: crear_plataforma(e.plataforma) for e in catalogo.empresas}
        ajustes = ajustes_llm or AjustesLLM()
        proveedores = ajustes_proveedores or AjustesProveedores()
    except (
        ConfiguracionInvalida,
        PlataformaDesconocida,
        ParametrosPlataformaInvalidos,
        ValidationError,
    ) as error:
        raise ErrorArranque(str(error)) from error
    analizador = crear_analizador(ajustes)
    # Un adaptador por tipo; la URL, el timeout y los reintentos van en el YAML de cada empresa.
    proveedores_prioridad = (
        {"http": ProveedorPrioridadHTTP()} if proveedores.prioridad_externa == "activa" else {}
    )
    registro.info(
        "arranque empresas=%d carpeta=%s llm=%s prioridad_externa=%s",
        len(catalogo),
        carpeta.name,
        ajustes.llm_modelo if analizador else "reglas",
        proveedores.prioridad_externa,
    )
    return CasoDeUsoTriage(
        catalogo=catalogo,
        plataformas=plataformas,
        analizador=analizador,
        proveedores_prioridad=proveedores_prioridad,
    )
