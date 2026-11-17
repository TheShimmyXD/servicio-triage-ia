"""Puertos hacia el mundo de afuera: LLM, plataformas, prioridad y solicitudes atendidas.

El caso de uso solo conoce estas interfaces; services/ trae las implementaciones y
app/ las conecta. Así cambiar de proveedor o sumar una plataforma no toca el triage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.contrato import DocumentoCliente, Prioridad
from domain.duplicados import SolicitudAtendida
from domain.empresa import ConfiguracionEmpresa


@dataclass(frozen=True)
class AnalisisLLM:
    """Lo que el LLM devuelve ya validado contra el esquema (la categoría se revisa aparte)."""

    categoria: str
    informacion_suficiente: bool
    hechos: str | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None


class ErrorLLM(RuntimeError):
    """Timeout, error HTTP o salida que no cumple el esquema. Activa el respaldo por reglas."""


class AnalizadorLLM(Protocol):
    def analizar(self, texto: str, empresa: ConfiguracionEmpresa) -> AnalisisLLM:
        """Clasifica dentro de las categorías de la empresa y extrae los datos del cliente."""
        ...


@dataclass(frozen=True)
class CasoExterno:
    """Lo que se envía a la plataforma de la empresa para abrir el caso."""

    compania: str
    solicitud_id: str
    categoria: str | None
    prioridad: Prioridad | None
    documento: DocumentoCliente | None
    descripcion: str
    justificacion: str


class ErrorPlataforma(RuntimeError):
    """La plataforma de casos no respondió o rechazó el caso."""


class PlataformaCasos(Protocol):
    def crear_caso(self, caso: CasoExterno) -> str:
        """Crea el caso y devuelve su id en la plataforma de la empresa."""
        ...


class ErrorProveedorPrioridad(RuntimeError):
    """El servicio de prioridad del cliente falló; se usan las reglas de la empresa."""


class ProveedorPrioridad(Protocol):
    def obtener(
        self,
        empresa: ConfiguracionEmpresa,
        documento: DocumentoCliente | None,
        categoria: str | None,
    ) -> Prioridad:
        """Prioridad según el servicio externo del cliente."""
        ...


class RepositorioSolicitudes(Protocol):
    """Solicitudes ya atendidas por (compania, solicitud_id). En memoria hoy; en la nube,
    una tabla con esa clave única (por ejemplo, DynamoDB o Postgres)."""

    def obtener(self, compania: str, solicitud_id: str) -> SolicitudAtendida | None: ...

    def guardar(self, compania: str, solicitud_id: str, atendida: SolicitudAtendida) -> None: ...
