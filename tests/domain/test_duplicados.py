from __future__ import annotations

from dataclasses import replace
from datetime import date

from domain.contrato import EstadoCaso, ProximoPaso, ResultadoTriage
from domain.duplicados import (
    AccionAnteDuplicado,
    SolicitudAtendida,
    decidir_ante_duplicado,
    normalizar_texto,
)

RESULTADO = ResultadoTriage(
    "GASES DEL ORINOCO",
    "REQ-001",
    date(2026, 11, 17),
    "Incidente técnico",
    None,
    None,
    None,
    "ZD-000001",
    ProximoPaso.GESTION_EXTERNA,
    "motivo",
    EstadoCaso.PENDIENTE,
)
PREVIA = SolicitudAtendida("la estufa no prende", RESULTADO)


def test_sin_registro_es_nueva():
    assert decidir_ante_duplicado(None, "texto") is AccionAnteDuplicado.NUEVA


def test_mismo_texto_devuelve_el_existente_aunque_cambien_los_espacios():
    accion = decidir_ante_duplicado(PREVIA, "  la estufa   no prende\n")
    assert accion is AccionAnteDuplicado.DEVOLVER_EXISTENTE


def test_otro_texto_es_conflicto():
    assert decidir_ante_duplicado(PREVIA, "otra cosa") is AccionAnteDuplicado.CONFLICTO


def test_si_la_plataforma_fallo_se_reintenta():
    fallida = replace(PREVIA, resultado=replace(RESULTADO, estado=EstadoCaso.ERROR_PLATAFORMA))
    assert decidir_ante_duplicado(fallida, "la estufa no prende") is AccionAnteDuplicado.REINTENTAR


def test_normalizar_texto():
    assert normalizar_texto(" a \t b\n c ") == "a b c"
