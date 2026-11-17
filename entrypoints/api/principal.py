"""Puerta HTTP del servicio de triage."""

from __future__ import annotations

from fastapi import FastAPI

aplicacion = FastAPI(
    title="Servicio de triage de solicitudes",
    version="0.1.0",
)


@aplicacion.get("/salud")
def salud() -> dict[str, str]:
    """Responde si el proceso está arriba; sirve para el chequeo del orquestador."""
    return {"estado": "ok"}
