"""Puerta HTTP del servicio de triage.

Solo traduce: JSON -> Solicitud, el caso de uso decide, ResultadoTriage -> JSON. Los
errores salen siempre con código y mensaje; nunca un 500 sin explicación.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.composicion import construir_triage
from app.triage import CasoDeUsoTriage
from domain.contrato import Solicitud
from domain.empresa import EmpresaNoParametrizada
from entrypoints.api.esquemas import (
    EntradaSolicitud,
    ErrorCampo,
    SalidaEmpresas,
    SalidaError,
    SalidaTriage,
)

registro = logging.getLogger(__name__)


def _respuesta_error(estado_http: int, error: SalidaError) -> JSONResponse:
    return JSONResponse(status_code=estado_http, content=error.model_dump(exclude_none=True))


def crear_aplicacion(triage: CasoDeUsoTriage | None = None) -> FastAPI:
    """Arma la API. Las pruebas inyectan su caso de uso; uvicorn usa la configuración real."""
    caso_de_uso = triage or construir_triage()
    aplicacion = FastAPI(title="Servicio de triage de solicitudes", version="0.1.0")

    @aplicacion.exception_handler(EmpresaNoParametrizada)
    def _empresa_no_parametrizada(_: Request, error: EmpresaNoParametrizada) -> JSONResponse:
        registro.warning("empresa_no_parametrizada compania=%r", error.nombre)
        return _respuesta_error(
            404,
            SalidaError(
                codigo=error.codigo, mensaje=str(error), empresas_validas=list(error.validas)
            ),
        )

    @aplicacion.exception_handler(RequestValidationError)
    def _entrada_invalida(_: Request, error: RequestValidationError) -> JSONResponse:
        errores = [
            ErrorCampo(
                campo=".".join(str(p) for p in e["loc"] if p != "body") or "cuerpo",
                problema=e["msg"],
            )
            for e in error.errors()
        ]
        registro.warning("entrada_invalida campos=%s", [e.campo for e in errores])
        return _respuesta_error(
            422,
            SalidaError(
                codigo="ENTRADA_INVALIDA",
                mensaje="La solicitud no cumple el contrato de entrada.",
                errores=errores,
            ),
        )

    @aplicacion.exception_handler(Exception)
    def _error_interno(_: Request, error: Exception) -> JSONResponse:
        registro.exception("error_interno tipo=%s", type(error).__name__)
        return _respuesta_error(
            500,
            SalidaError(codigo="ERROR_INTERNO", mensaje="Error inesperado; quedó en el log."),
        )

    @aplicacion.get("/salud")
    def salud() -> dict[str, str]:
        """Responde si el proceso está arriba; sirve para el chequeo del orquestador."""
        return {"estado": "ok"}

    @aplicacion.get("/empresas", response_model=SalidaEmpresas)
    def empresas() -> SalidaEmpresas:
        """Empresas parametrizadas: las que el servicio sabe atender."""
        return SalidaEmpresas(empresas=list(caso_de_uso.catalogo.nombres))

    @aplicacion.post(
        "/solicitudes",
        response_model=SalidaTriage,
        responses={404: {"model": SalidaError}, 422: {"model": SalidaError}},
    )
    def triage_solicitud(entrada: EntradaSolicitud) -> SalidaTriage:
        """Hace el triage de una solicitud y, si es gestión externa, crea el caso."""
        solicitud = Solicitud(**entrada.model_dump())
        resultado = caso_de_uso.ejecutar(solicitud)
        return SalidaTriage.model_validate(resultado.a_diccionario())

    return aplicacion


aplicacion = crear_aplicacion()
