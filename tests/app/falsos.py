"""Dobles de prueba de los puertos: ninguna prueba sale a la red."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.contrato import DocumentoCliente, Prioridad
from domain.empresa import ConfiguracionEmpresa
from domain.puertos import (
    AnalisisLLM,
    CasoExterno,
    ErrorLLM,
    ErrorPlataforma,
    ErrorProveedorPrioridad,
    ErrorProveedorPrioridadSinRespuesta,
)


@dataclass
class AnalizadorFalso:
    respuesta: AnalisisLLM | None = None
    error: str | None = None
    llamados: int = 0

    def analizar(self, texto: str, empresa: ConfiguracionEmpresa) -> AnalisisLLM:
        self.llamados += 1
        if self.error:
            raise ErrorLLM(self.error)
        assert self.respuesta is not None
        return self.respuesta


@dataclass
class PlataformaFalsa:
    prefijo: str
    casos: list[CasoExterno] = field(default_factory=list)
    fallas_pendientes: int = 0
    llamadas: int = 0

    def crear_caso(self, caso: CasoExterno) -> str:
        self.llamadas += 1
        if self.fallas_pendientes > 0:
            self.fallas_pendientes -= 1
            raise ErrorPlataforma("timeout de 5 s")
        self.casos.append(caso)
        return f"{self.prefijo}-{len(self.casos):06d}"


@dataclass
class ProveedorPrioridadFalso:
    prioridad: Prioridad = Prioridad.ALTA
    falla: bool = False
    sin_respuesta: bool = False
    pedidos: list[tuple[DocumentoCliente | None, str | None]] = field(default_factory=list)

    def obtener(
        self,
        empresa: ConfiguracionEmpresa,
        documento: DocumentoCliente | None,
        categoria: str | None,
    ) -> Prioridad:
        self.pedidos.append((documento, categoria))
        if self.sin_respuesta:
            raise ErrorProveedorPrioridadSinRespuesta("no respondió tras 3 intentos")
        if self.falla:
            raise ErrorProveedorPrioridad("rechazó el pedido")
        return self.prioridad
