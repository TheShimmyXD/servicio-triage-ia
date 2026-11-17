"""Raíz de composición: lee la configuración y arma el caso de uso con sus servicios.

Se ejecuta una vez al arrancar. Si la configuración no sirve, el servicio no arranca y
dice por qué: es mejor que responder con una empresa a medio configurar.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.triage import CasoDeUsoTriage
from services.configuracion_empresas import (
    CARPETA_POR_DEFECTO,
    ConfiguracionInvalida,
    cargar_catalogo,
)
from services.plataformas_simuladas import PlataformaDesconocida, crear_plataforma

registro = logging.getLogger(__name__)


class ErrorArranque(RuntimeError):
    """Configuración de empresas o de plataformas que no permite arrancar."""


def construir_triage(carpeta_empresas: Path | None = None) -> CasoDeUsoTriage:
    carpeta = carpeta_empresas or CARPETA_POR_DEFECTO
    try:
        catalogo = cargar_catalogo(carpeta)
        plataformas = {e.nombre: crear_plataforma(e.plataforma) for e in catalogo.empresas}
    except (ConfiguracionInvalida, PlataformaDesconocida) as error:
        raise ErrorArranque(str(error)) from error
    registro.info("arranque empresas=%d carpeta=%s", len(catalogo), carpeta.name)
    return CasoDeUsoTriage(catalogo=catalogo, plataformas=plataformas)
