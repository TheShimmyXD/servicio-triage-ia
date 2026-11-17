"""Contrato HTTP: entrada y salida del ejemplo del enunciado y la forma de los errores."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from domain.contrato import EstadoCaso, Prioridad, ProximoPaso

EJEMPLO_REQ_001 = {
    "compania": "GASES DEL ORINOCO",
    "solicitud_id": "REQ-001",
    "solicitud_descripcion": (
        "Mi nombre es Juana y mi numero de cédula es 102045678 . Solicito una revision "
        "urgente porque la estufa qué compre hace 2 semanas con la empresa presenta fallas "
        "(no está haciendo contacto con la llave del gas) "
    ),
}


class EntradaSolicitud(BaseModel):
    """Los tres campos del ejemplo de INPUT. Los topes de longitud son supuestos."""

    model_config = ConfigDict(
        str_strip_whitespace=True, json_schema_extra={"examples": [EJEMPLO_REQ_001]}
    )

    compania: str = Field(min_length=1, max_length=120)
    solicitud_id: str = Field(min_length=1, max_length=64)
    # El tope evita textos que inflen el costo del LLM sin aportar al triage.
    solicitud_descripcion: str = Field(min_length=1, max_length=5000)


class SalidaTriage(BaseModel):
    """Los campos del ejemplo de OUTPUT, en su orden."""

    compania: str
    solicitud_id: str
    solicitud_fecha: date
    solicitud_tipo: str | None
    solicitud_prioridad: Prioridad | None
    solicitud_tipo_id_cliente: str | None
    solicitud_id_cliente: str | None
    solicitud_id_plataforma_externa: str | None
    proximo_paso: ProximoPaso
    justificacion: str
    estado: EstadoCaso


class SalidaEmpresas(BaseModel):
    empresas: list[str]


class ErrorCampo(BaseModel):
    campo: str
    problema: str


class SalidaError(BaseModel):
    """Todo error lleva un código estable para el cliente y un mensaje para la persona."""

    codigo: str
    mensaje: str
    empresas_validas: list[str] | None = None
    errores: list[ErrorCampo] | None = None
