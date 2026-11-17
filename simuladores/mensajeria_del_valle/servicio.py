"""Simulador del microservicio de prioridad que entrega MENSAJERIA DEL VALLE.

El enunciado solo fija el contrato: a partir de tipo_documento, numero_documento_cliente
y tipo_solicitud devuelve la prioridad del caso. Las reglas internas son supuestas,
fijas y distintas de las del triage, para que se note quién decidió:

1. Base por tipo de solicitud: paquete dañado o perdido -> Alta; envío retrasado o
   cambio de dirección -> Media; cualquier otro (o sin tipo) -> Baja.
2. Clientes corporativos (NIT) y clientes preferentes de la cartera suben un nivel.

Se levanta aparte del triage, como lo haría el servicio real del cliente:
    .venv/bin/uvicorn simuladores.mensajeria_del_valle.servicio:aplicacion --port 8001
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

NivelPrioridad = Literal["Alta", "Media", "Baja"]
NIVELES: tuple[NivelPrioridad, ...] = ("Baja", "Media", "Alta")

PRIORIDAD_POR_TIPO: dict[str, NivelPrioridad] = {
    "Paquete dañado o perdido": "Alta",
    "Envío retrasado": "Media",
    "Cambio de dirección": "Media",
}
CLIENTES_PREFERENTES = frozenset({"1144556677", "900123456"})
"""Cartera ficticia del simulador."""


class PedidoPrioridad(BaseModel):
    tipo_documento: str = Field(min_length=1, max_length=5)
    numero_documento_cliente: str = Field(min_length=1, max_length=20)
    tipo_solicitud: str | None = None


class RespuestaPrioridad(BaseModel):
    prioridad: NivelPrioridad
    motivo: str


def calcular_prioridad_cliente(pedido: PedidoPrioridad) -> RespuestaPrioridad:
    base = PRIORIDAD_POR_TIPO.get(pedido.tipo_solicitud or "", "Baja")
    numero = "".join(c for c in pedido.numero_documento_cliente if c.isalnum())
    if pedido.tipo_documento.upper() == "NIT":
        motivo = "cliente corporativo"
    elif numero in CLIENTES_PREFERENTES:
        motivo = "cliente preferente"
    else:
        return RespuestaPrioridad(prioridad=base, motivo=f"tipo de solicitud ({base})")
    subida = NIVELES[min(NIVELES.index(base) + 1, len(NIVELES) - 1)]
    return RespuestaPrioridad(prioridad=subida, motivo=f"{motivo}: sube de {base} a {subida}")


aplicacion = FastAPI(title="Prioridad de MENSAJERIA DEL VALLE (simulador)", version="0.1.0")


@aplicacion.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


@aplicacion.post("/prioridad", response_model=RespuestaPrioridad)
def prioridad(pedido: PedidoPrioridad) -> RespuestaPrioridad:
    return calcular_prioridad_cliente(pedido)
