"""Ajustes del servicio leídos del .env o de las variables de entorno (ver .env.example)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ARCHIVO_ENV = Path(__file__).resolve().parent.parent / ".env"


class AjustesLLM(BaseSettings):
    """Las variables de entorno mandan sobre el .env; la clave nunca se muestra en el log."""

    model_config = SettingsConfigDict(
        env_file=ARCHIVO_ENV, env_file_encoding="utf-8", extra="ignore"
    )

    llm_proveedor: Literal["groq", "ninguno"] = "groq"
    llm_modelo: str = "openai/gpt-oss-20b"
    llm_url_base: str = "https://api.groq.com/openai/v1"
    groq_api_key: SecretStr | None = None
    llm_timeout_s: float = Field(default=10.0, gt=0, le=60)
    llm_fallas_para_abrir: int = Field(default=3, ge=1)
    llm_pausa_cortocircuito_s: float = Field(default=30.0, gt=0, le=3600)

    @property
    def clave(self) -> str:
        """La clave en claro, solo para el encabezado del pedido. Vacía si no hay."""
        return self.groq_api_key.get_secret_value().strip() if self.groq_api_key else ""


class AjustesProveedores(BaseSettings):
    """Servicios externos de prioridad de los clientes (por ejemplo, MENSAJERIA DEL VALLE)."""

    model_config = SettingsConfigDict(
        env_file=ARCHIVO_ENV, env_file_encoding="utf-8", extra="ignore"
    )

    prioridad_externa: Literal["activa", "ninguna"] = "activa"
    """Con "ninguna" toda empresa prioriza con sus reglas; las pruebas la usan para no
    depender de un servicio que puede estar arriba o no."""


class AjustesConfiguracion(BaseSettings):
    """De dónde se cargan las empresas: así cada despliegue trae las suyas sin tocar el repo."""

    model_config = SettingsConfigDict(
        env_file=ARCHIVO_ENV, env_file_encoding="utf-8", extra="ignore"
    )

    carpeta_empresas: Path | None = None
    """Sin valor, configuracion/empresas/ del repositorio."""
