"""Configuración de una empresa ya validada y el catálogo de empresas parametrizadas.

El dominio solo conoce esta forma; de dónde sale (YAML, base de datos) lo decide
services/. Agregar una empresa, una categoría o una regla es agregar datos.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from domain.contrato import ProximoPaso
from domain.documento_cliente import TiposDocumento
from domain.informacion_minima import REQUERIDOS_POR_DEFECTO, ElementoMinimo
from domain.prioridad import ReglasPrioridad
from domain.texto import normalizar_nombre


@dataclass(frozen=True)
class Categoria:
    """Categoría operativa: la descripción orienta al LLM y las palabras clave al respaldo."""

    nombre: str
    descripcion: str
    palabras_clave: tuple[str, ...]


@dataclass(frozen=True)
class ReglasInformacionMinima:
    """Qué elementos del paso 1 exige la empresa y qué frases propias cuentan como cada uno."""

    requeridos: frozenset[ElementoMinimo] = REQUERIDOS_POR_DEFECTO
    frases_extra: Mapping[ElementoMinimo, tuple[str, ...]] = field(default_factory=dict)
    por_categoria: Mapping[str, frozenset[ElementoMinimo]] = field(default_factory=dict)
    """Excepciones por categoría: una consulta de horarios no tiene "cuándo ocurrió"."""

    def requeridos_para(self, categoria: str | None) -> frozenset[ElementoMinimo]:
        """Lo que exige la categoría si tiene excepción; si no, lo general de la empresa."""
        if categoria is None:
            return self.requeridos
        return self.por_categoria.get(categoria, self.requeridos)


@dataclass(frozen=True)
class ConfiguracionPlataforma:
    """Plataforma de casos de la empresa: nombre en el registro y sus parámetros."""

    nombre: str
    parametros: Mapping[str, Any] = field(default_factory=dict)
    intentos: int = 3
    """Intentos de crear el caso antes de marcarlo como error de plataforma."""
    espera_inicial_s: float = 0.2
    """Espera antes del segundo intento; se duplica en cada uno."""


@dataclass(frozen=True)
class ConfiguracionProveedorPrioridad:
    """Quién decide la prioridad: las reglas propias o un servicio HTTP del cliente."""

    tipo: str = "reglas"
    url: str | None = None
    timeout_s: float = 2.0
    reintentos: int = 0
    fallas_para_abrir: int = 3
    """Veces seguidas sin respuesta que abren su cortocircuito."""
    pausa_s: float = 30.0
    """Segundos en que, abierto el cortocircuito, se usan las reglas sin llamarlo."""


@dataclass(frozen=True)
class ConfiguracionEmpresa:
    nombre: str
    categorias: tuple[Categoria, ...]
    reglas_prioridad: ReglasPrioridad
    delegaciones: Mapping[str, ProximoPaso]
    informacion_minima: ReglasInformacionMinima
    plataforma: ConfiguracionPlataforma
    proveedor_prioridad: ConfiguracionProveedorPrioridad
    tipos_documento: TiposDocumento
    """La lista global de tipos de documento: la usan las reglas, el LLM y su verificación."""

    @property
    def nombres_categorias(self) -> tuple[str, ...]:
        return tuple(c.nombre for c in self.categorias)


class EmpresaNoParametrizada(LookupError):
    """La solicitud nombra una empresa sin configuración. La API la vuelve un 404 claro."""

    codigo = "EMPRESA_NO_PARAMETRIZADA"

    def __init__(self, nombre: str, validas: Iterable[str]) -> None:
        self.nombre = nombre
        self.validas = tuple(sorted(validas))
        super().__init__(
            f'La empresa "{nombre}" no está parametrizada. Válidas: {", ".join(self.validas)}'
        )


class CatalogoEmpresas:
    """Empresas por nombre normalizado: "Gases del Orinoco" y "GASES DEL ORINOCO" son la misma."""

    def __init__(self, empresas: Iterable[ConfiguracionEmpresa]) -> None:
        self._por_nombre: dict[str, ConfiguracionEmpresa] = {}
        for empresa in empresas:
            clave = normalizar_nombre(empresa.nombre)
            if clave in self._por_nombre:
                raise ValueError(f'Empresa repetida en la configuración: "{empresa.nombre}"')
            self._por_nombre[clave] = empresa

    def obtener(self, nombre: str) -> ConfiguracionEmpresa:
        try:
            return self._por_nombre[normalizar_nombre(nombre)]
        except KeyError:
            raise EmpresaNoParametrizada(nombre, self.nombres) from None

    @property
    def nombres(self) -> tuple[str, ...]:
        return tuple(sorted(e.nombre for e in self._por_nombre.values()))

    @property
    def empresas(self) -> tuple[ConfiguracionEmpresa, ...]:
        return tuple(self._por_nombre.values())

    def __len__(self) -> int:
        return len(self._por_nombre)
