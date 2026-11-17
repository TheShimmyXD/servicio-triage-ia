"""Proveedor de prioridad por HTTP: el microservicio que entrega el cliente.

Contrato del enunciado (bono de personalización): con tipo_documento,
numero_documento_cliente y tipo_solicitud devuelve la prioridad. La URL, el timeout y
los reintentos salen del YAML de la empresa, así que otro cliente con su propio servicio
se suma solo con su archivo. Toda falla termina en ErrorProveedorPrioridad y el triage
usa las reglas de la empresa.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx2
from pydantic import BaseModel, ValidationError

from domain.contrato import DocumentoCliente, Prioridad
from domain.empresa import ConfiguracionEmpresa
from domain.puertos import ErrorProveedorPrioridad

registro = logging.getLogger(__name__)

ESPERA_INICIAL_S = 0.2


class _RespuestaPrioridad(BaseModel):
    prioridad: Prioridad


class _FallaReintentable(Exception):
    """Timeout, red caída o 5xx: puede pasar en el siguiente intento."""


class ProveedorPrioridadHTTP:
    def __init__(
        self,
        transporte: httpx2.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cliente = httpx2.Client(transport=transporte)
        self._dormir = dormir

    def obtener(
        self,
        empresa: ConfiguracionEmpresa,
        documento: DocumentoCliente | None,
        categoria: str | None,
    ) -> Prioridad:
        configuracion = empresa.proveedor_prioridad
        if not configuracion.url:
            raise ErrorProveedorPrioridad("la empresa no tiene URL de su servicio")
        if documento is None:
            # El contrato del cliente exige el documento: sin él no se llama.
            raise ErrorProveedorPrioridad("la solicitud no trae el documento del cliente")
        pedido = {
            "tipo_documento": documento.tipo,
            "numero_documento_cliente": documento.numero,
            "tipo_solicitud": categoria,
        }
        intentos = configuracion.reintentos + 1
        motivo = ""
        for intento in range(1, intentos + 1):
            try:
                return self._pedir(configuracion.url, pedido, configuracion.timeout_s)
            except _FallaReintentable as error:
                motivo = str(error)
                registro.warning(
                    "proveedor_prioridad_fallo empresa=%s intento=%d/%d error=%s",
                    empresa.nombre,
                    intento,
                    intentos,
                    motivo,
                )
                if intento < intentos:
                    self._dormir(ESPERA_INICIAL_S * 2 ** (intento - 1))
        raise ErrorProveedorPrioridad(f"no respondió tras {intentos} intentos: {motivo}")

    def _pedir(self, url: str, pedido: dict[str, str | None], timeout_s: float) -> Prioridad:
        try:
            respuesta = self._cliente.post(url, json=pedido, timeout=timeout_s)
        except httpx2.TimeoutException as error:
            raise _FallaReintentable("timeout") from error
        except httpx2.HTTPError as error:
            raise _FallaReintentable(f"error de red {type(error).__name__}") from error
        if respuesta.status_code >= 500:
            raise _FallaReintentable(f"HTTP {respuesta.status_code}")
        if respuesta.status_code != 200:
            # Un 4xx no cambia al repetir: el pedido no le sirve al cliente.
            raise ErrorProveedorPrioridad(f"rechazó el pedido (HTTP {respuesta.status_code})")
        try:
            return _RespuestaPrioridad.model_validate_json(respuesta.content).prioridad
        except ValidationError as error:
            raise ErrorProveedorPrioridad("respondió sin una prioridad válida") from error
