"""Contrato de entrada y salida del triage.

Origen: enunciado, "Ejemplo del INPUT/OUTPUT" y requerimiento 5. El ejemplo de salida
tiene los valores del documento cruzados; aquí cada valor va en su campo lógico
(solicitud_tipo_id_cliente = "CC", solicitud_id_cliente = el número) y el próximo paso
usa los valores del requerimiento. La diferencia se explica en el README.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Prioridad(StrEnum):
    """Niveles del paso 3 del proceso (Alta/Media/Baja)."""

    ALTA = "Alta"
    MEDIA = "Media"
    BAJA = "Baja"

    @property
    def peso(self) -> int:
        """Orden para quedarse con la mayor cuando varias reglas aplican."""
        return {"Alta": 3, "Media": 2, "Baja": 1}[self.value]


class ProximoPaso(StrEnum):
    """Valores literales del requerimiento 5."""

    GESTION_EXTERNA = "GESTION_EXTERNA"
    RESPUESTA_DIRECTA = "RESPUESTA_DIRECTA"
    CIERRE_POR_INFORMACION_INSUFICIENTE = "CIERRE_POR_INFORMACION_INSUFICIENTE"


class EstadoCaso(StrEnum):
    """Estado del caso tras el triage.

    "pendiente" sale del ejemplo y del paso 6 (queda abierto hasta que la empresa lo
    resuelva). "cerrado" es supuesto: los pasos 1 y 7 dicen que el BPO cierra el caso,
    pero el enunciado no fija la palabra.
    """

    PENDIENTE = "pendiente"
    CERRADO = "cerrado"
    ERROR_PLATAFORMA = "error_plataforma"
    """Supuesto: la gestión externa no se pudo crear tras los reintentos. El motivo va en
    la justificación y reenviar la misma solicitud vuelve a intentarlo."""


JUSTIFICACION_INFORMACION_INSUFICIENTE = "Información incompleta o faltante"
"""Texto literal del paso 1 del proceso para el cierre inmediato."""


@dataclass(frozen=True)
class Solicitud:
    """Entrada del servicio: los tres campos del ejemplo de INPUT."""

    compania: str
    solicitud_id: str
    solicitud_descripcion: str


@dataclass(frozen=True)
class DocumentoCliente:
    """Documento del cliente encontrado en el texto (tipo abreviado y número limpio)."""

    tipo: str
    numero: str


@dataclass(frozen=True)
class ResultadoTriage:
    """Salida del servicio con los campos del ejemplo de OUTPUT.

    solicitud_fecha es la fecha de recepción (supuesto: la entrada no trae fecha).
    """

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

    def a_diccionario(self) -> dict[str, str | None]:
        """Diccionario en el orden del ejemplo, con la fecha en ISO y los enums como texto."""
        return {
            "compania": self.compania,
            "solicitud_id": self.solicitud_id,
            "solicitud_fecha": self.solicitud_fecha.isoformat(),
            "solicitud_tipo": self.solicitud_tipo,
            "solicitud_prioridad": (
                self.solicitud_prioridad.value if self.solicitud_prioridad else None
            ),
            "solicitud_tipo_id_cliente": self.solicitud_tipo_id_cliente,
            "solicitud_id_cliente": self.solicitud_id_cliente,
            "solicitud_id_plataforma_externa": self.solicitud_id_plataforma_externa,
            "proximo_paso": self.proximo_paso.value,
            "justificacion": self.justificacion,
            "estado": self.estado.value,
        }
