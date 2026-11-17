"""Arma docs/documento_tecnico.pdf desde documento_tecnico.md y estilo.css.

Uso (desde la raíz del repositorio, con el extra docs instalado):

    pip install -e ".[docs]"
    python docs/construir_pdf.py

Convierte el Markdown a HTML y lo imprime a PDF con Chrome o Chromium sin encabezados.
El HTML intermedio se escribe junto al Markdown y se borra al terminar: el Chromium de
snap no puede leer /tmp.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

CARPETA = Path(__file__).resolve().parent
FUENTE = CARPETA / "documento_tecnico.md"
ESTILO = CARPETA / "estilo.css"
SALIDA = CARPETA / "documento_tecnico.pdf"
TITULO = "Servicio de triage de solicitudes - Documento técnico"
NAVEGADORES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def buscar_navegador() -> str:
    """Devuelve la ruta de Chrome o Chromium; la variable CHROME manda si está definida."""
    elegido = os.environ.get("CHROME")
    if elegido:
        return elegido
    for nombre in NAVEGADORES:
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    raise SystemExit("No se encontró Chrome ni Chromium. Defina CHROME con la ruta del ejecutable.")


def armar_html(texto_md: str, css: str) -> str:
    cuerpo = markdown.markdown(texto_md, extensions=["tables"])
    return (
        "<!doctype html>\n<html lang='es'><head><meta charset='utf-8'>"
        f"<title>{TITULO}</title><style>{css}</style></head>"
        f"<body>{cuerpo}</body></html>"
    )


def construir() -> Path:
    html = armar_html(FUENTE.read_text(encoding="utf-8"), ESTILO.read_text(encoding="utf-8"))
    intermedio = CARPETA / "_documento_tecnico.html"
    intermedio.write_text(html, encoding="utf-8")
    try:
        orden = [
            buscar_navegador(),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={SALIDA}",
            intermedio.as_uri(),
        ]
        resultado = subprocess.run(orden, capture_output=True, text=True, check=False)
    finally:
        intermedio.unlink(missing_ok=True)
    if resultado.returncode != 0 or not SALIDA.exists():
        raise SystemExit(f"El navegador no generó el PDF:\n{resultado.stderr[-800:]}")
    return SALIDA


if __name__ == "__main__":
    ruta = construir()
    print(f"PDF generado: {ruta}", file=sys.stdout)
