"""Carga y validación de la configuración de empresas desde YAML.

Un archivo por empresa en configuracion/empresas/. Todo se valida al arrancar: un
archivo mal formado detiene el servicio con el archivo y el campo culpables, en vez de
fallar a mitad de una solicitud.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from domain.contrato import Prioridad, ProximoPaso
from domain.empresa import (
    CatalogoEmpresas,
    Categoria,
    ConfiguracionEmpresa,
    ConfiguracionPlataforma,
    ConfiguracionProveedorPrioridad,
    ReglasInformacionMinima,
)
from domain.informacion_minima import ElementoMinimo
from domain.prioridad import ReglasPrioridad, SenalPrioridad
from domain.texto import normalizar

CARPETA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "configuracion" / "empresas"

TextoNoVacio = Annotated[str, Field(min_length=1)]


class _Estricto(BaseModel):
    # Un campo mal escrito ("delegacion") es un error, no un valor por defecto silencioso.
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Categoria(_Estricto):
    nombre: TextoNoVacio
    descripcion: TextoNoVacio
    palabras_clave: list[TextoNoVacio] = Field(min_length=1)


class _Senal(_Estricto):
    prioridad: Prioridad
    frases: list[TextoNoVacio] = Field(min_length=1)


class _ReglasPrioridad(_Estricto):
    por_defecto: Prioridad
    por_categoria: dict[str, Prioridad] = Field(default_factory=dict)
    senales: list[_Senal] = Field(default_factory=list)


class _InformacionMinima(_Estricto):
    requeridos: list[ElementoMinimo] = Field(default_factory=lambda: list(ElementoMinimo))
    frases_extra: dict[ElementoMinimo, list[TextoNoVacio]] = Field(default_factory=dict)


class _Plataforma(_Estricto):
    nombre: TextoNoVacio
    parametros: dict[str, Any] = Field(default_factory=dict)
    intentos: int = Field(default=3, ge=1, le=10)
    espera_inicial_s: float = Field(default=0.2, ge=0, le=10)


class _ProveedorReglas(_Estricto):
    tipo: Literal["reglas"] = "reglas"


class _ProveedorHttp(_Estricto):
    tipo: Literal["http"]
    url: Annotated[str, Field(pattern=r"^https?://")]
    timeout_s: float = Field(default=2.0, gt=0, le=30)
    reintentos: int = Field(default=2, ge=0, le=5)
    fallas_para_abrir: int = Field(default=3, ge=1, le=20)
    pausa_s: float = Field(default=30.0, gt=0, le=600)


class _Empresa(_Estricto):
    nombre: TextoNoVacio
    categorias: list[_Categoria] = Field(min_length=1)
    reglas_prioridad: _ReglasPrioridad
    delegaciones: dict[str, Literal["GESTION_EXTERNA", "RESPUESTA_DIRECTA"]]
    informacion_minima: _InformacionMinima = Field(default_factory=_InformacionMinima)
    plataforma: _Plataforma
    proveedor_prioridad: Annotated[
        _ProveedorReglas | _ProveedorHttp, Field(discriminator="tipo")
    ] = Field(default_factory=_ProveedorReglas)

    @model_validator(mode="after")
    def _categorias_coherentes(self) -> _Empresa:
        """Toda categoría tiene delegación y ninguna regla nombra una categoría que no existe."""
        nombres = [c.nombre for c in self.categorias]
        normalizados = [normalizar(n) for n in nombres]
        if len(set(normalizados)) != len(normalizados):
            raise ValueError(f"categorías repetidas: {nombres}")
        conocidas = set(nombres)
        sin_delegacion = conocidas - set(self.delegaciones)
        if sin_delegacion:
            raise ValueError(f"categorías sin delegación: {sorted(sin_delegacion)}")
        sobrantes = set(self.delegaciones) - conocidas
        if sobrantes:
            raise ValueError(f"delegaciones de categorías que no existen: {sorted(sobrantes)}")
        desconocidas = set(self.reglas_prioridad.por_categoria) - conocidas
        if desconocidas:
            raise ValueError(
                f"reglas_prioridad.por_categoria nombra categorías que no existen: "
                f"{sorted(desconocidas)}"
            )
        return self

    def a_dominio(self) -> ConfiguracionEmpresa:
        proveedor = self.proveedor_prioridad
        return ConfiguracionEmpresa(
            nombre=self.nombre,
            categorias=tuple(
                Categoria(c.nombre, c.descripcion, tuple(c.palabras_clave)) for c in self.categorias
            ),
            reglas_prioridad=ReglasPrioridad(
                por_defecto=self.reglas_prioridad.por_defecto,
                por_categoria=dict(self.reglas_prioridad.por_categoria),
                senales=tuple(
                    SenalPrioridad(s.prioridad, tuple(s.frases))
                    for s in self.reglas_prioridad.senales
                ),
            ),
            delegaciones={c: ProximoPaso(p) for c, p in self.delegaciones.items()},
            informacion_minima=ReglasInformacionMinima(
                requeridos=frozenset(self.informacion_minima.requeridos),
                frases_extra={e: tuple(f) for e, f in self.informacion_minima.frases_extra.items()},
            ),
            plataforma=ConfiguracionPlataforma(
                self.plataforma.nombre,
                dict(self.plataforma.parametros),
                intentos=self.plataforma.intentos,
                espera_inicial_s=self.plataforma.espera_inicial_s,
            ),
            proveedor_prioridad=(
                ConfiguracionProveedorPrioridad(
                    tipo="http",
                    url=proveedor.url,
                    timeout_s=proveedor.timeout_s,
                    reintentos=proveedor.reintentos,
                    fallas_para_abrir=proveedor.fallas_para_abrir,
                    pausa_s=proveedor.pausa_s,
                )
                if isinstance(proveedor, _ProveedorHttp)
                else ConfiguracionProveedorPrioridad()
            ),
        )


class ConfiguracionInvalida(ValueError):
    """Un archivo de empresa no cumple el esquema. El mensaje nombra archivo y campo."""


def _describir_errores(archivo: Path, error: ValidationError) -> str:
    lineas = [f"{archivo.name}: configuración inválida"]
    for detalle in error.errors():
        ubicacion = ".".join(str(parte) for parte in detalle["loc"]) or "(raíz)"
        lineas.append(f"  - {ubicacion}: {detalle['msg']}")
    return "\n".join(lineas)


def cargar_empresa(archivo: Path) -> ConfiguracionEmpresa:
    """Lee y valida un YAML de empresa."""
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfiguracionInvalida(f"{archivo.name}: YAML mal formado: {error}") from error
    if not isinstance(datos, dict):
        raise ConfiguracionInvalida(f"{archivo.name}: se esperaba un mapa con la empresa")
    try:
        return _Empresa.model_validate(datos).a_dominio()
    except ValidationError as error:
        raise ConfiguracionInvalida(_describir_errores(archivo, error)) from error


def cargar_catalogo(carpeta: Path = CARPETA_POR_DEFECTO) -> CatalogoEmpresas:
    """Carga todas las empresas de la carpeta. Sin empresas, el servicio no tiene sentido."""
    archivos = sorted([*carpeta.glob("*.yaml"), *carpeta.glob("*.yml")])
    if not archivos:
        raise ConfiguracionInvalida(f"No hay archivos de empresa en {carpeta}")
    try:
        return CatalogoEmpresas(cargar_empresa(a) for a in archivos)
    except ValueError as error:
        if isinstance(error, ConfiguracionInvalida):
            raise
        raise ConfiguracionInvalida(str(error)) from error
