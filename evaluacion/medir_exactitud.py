"""Mide la exactitud del triage con reglas y con el LLM sobre el conjunto etiquetado.

Uso, desde la raíz del repositorio:

    python -m evaluacion.medir_exactitud            # reglas y, si hay GROQ_API_KEY, LLM
    python -m evaluacion.medir_exactitud --detalle  # además, cada solicitud que falla

Arma el triage igual que el servicio (app/composicion), pero sin el proveedor externo de
prioridad: la prioridad no se mide aquí y así no hace falta levantar el simulador.
"""

from __future__ import annotations

import argparse
import logging
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.composicion import construir_triage
from app.metricas import Evento
from domain.contrato import ProximoPaso, Solicitud
from services.ajustes import AjustesLLM, AjustesProveedores

ARCHIVO_CONJUNTO = Path(__file__).resolve().parent / "solicitudes_etiquetadas.yaml"


@dataclass(frozen=True)
class Etiquetada:
    id: str
    compania: str
    descripcion: str
    categoria: str | None
    proximo_paso: ProximoPaso

    @property
    def suficiente(self) -> bool:
        return self.proximo_paso is not ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE


@dataclass(frozen=True)
class Fallo:
    id: str
    esperado: str
    obtenido: str


@dataclass
class Medicion:
    modo: str
    total: int = 0
    con_categoria: int = 0
    categoria_ok: int = 0
    suficiencia_ok: int = 0
    paso_ok: int = 0
    respaldos: int = 0
    """Solicitudes en que el LLM falló o respondió fuera de lo permitido y atendieron las reglas."""
    latencias_ms: list[float] | None = None
    fallos: list[Fallo] | None = None

    @property
    def latencia_mediana_ms(self) -> float:
        return statistics.median(self.latencias_ms) if self.latencias_ms else 0.0


def cargar_conjunto(archivo: Path = ARCHIVO_CONJUNTO) -> list[Etiquetada]:
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    return [
        Etiquetada(
            id=fila["id"],
            compania=fila["compania"],
            descripcion=fila["descripcion"],
            categoria=fila["categoria"],
            proximo_paso=ProximoPaso(fila["proximo_paso"]),
        )
        for fila in datos["solicitudes"]
    ]


def medir(
    conjunto: list[Etiquetada], ajustes_llm: AjustesLLM, modo: str, pausa_s: float = 0.0
) -> Medicion:
    # Un triage nuevo por medición: el registro de duplicados empieza vacío.
    triage = construir_triage(
        ajustes_llm=ajustes_llm,
        ajustes_proveedores=AjustesProveedores(prioridad_externa="ninguna"),
    )
    medicion = Medicion(modo=modo, latencias_ms=[], fallos=[])
    for indice, caso in enumerate(conjunto):
        # El plan gratuito de Groq limita las solicitudes por minuto (HTTP 429).
        if pausa_s and indice:
            time.sleep(pausa_s)
        inicio = time.perf_counter()
        resultado = triage.ejecutar(Solicitud(caso.compania, caso.id, caso.descripcion))
        medicion.latencias_ms.append((time.perf_counter() - inicio) * 1000)
        medicion.total += 1
        obtenido_suficiente = (
            resultado.proximo_paso is not ProximoPaso.CIERRE_POR_INFORMACION_INSUFICIENTE
        )
        medicion.suficiencia_ok += obtenido_suficiente == caso.suficiente
        if resultado.proximo_paso is caso.proximo_paso:
            medicion.paso_ok += 1
        else:
            medicion.fallos.append(
                Fallo(caso.id, caso.proximo_paso.value, resultado.proximo_paso.value)
            )
        # La categoría solo se exige cuando hay información para asignarla.
        if caso.categoria is not None:
            medicion.con_categoria += 1
            if resultado.solicitud_tipo == caso.categoria:
                medicion.categoria_ok += 1
            else:
                medicion.fallos.append(
                    Fallo(caso.id, caso.categoria, str(resultado.solicitud_tipo))
                )
    medicion.respaldos = triage.metricas.contar(Evento.LLM_FALLIDO)
    return medicion


def _porcentaje(aciertos: int, total: int) -> str:
    return f"{aciertos}/{total} ({100 * aciertos / total:.0f} %)" if total else "-"


def imprimir(mediciones: list[Medicion], detalle: bool) -> None:
    print(
        f"{'Modo':<26}{'Categoría':<16}{'Info. mínima':<16}{'Próximo paso':<16}"
        f"{'Latencia med.':<15}Respaldos"
    )
    for m in mediciones:
        print(
            f"{m.modo:<26}{_porcentaje(m.categoria_ok, m.con_categoria):<16}"
            f"{_porcentaje(m.suficiencia_ok, m.total):<16}{_porcentaje(m.paso_ok, m.total):<16}"
            f"{m.latencia_mediana_ms:>9.1f} ms    {m.respaldos}"
        )
    if detalle:
        for m in mediciones:
            for fallo in m.fallos or []:
                print(
                    f"  [{m.modo}] {fallo.id}: esperado {fallo.esperado!r}, "
                    f"obtenido {fallo.obtenido!r}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detalle", action="store_true", help="muestra cada fallo")
    parser.add_argument(
        "--pausa",
        type=float,
        default=8.0,
        help="segundos entre solicitudes al LLM (límite por minuto del proveedor)",
    )
    args = parser.parse_args()
    # Solo advertencias: el registro por solicitud taparía la tabla.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    conjunto = cargar_conjunto()
    suficientes = sum(caso.suficiente for caso in conjunto)
    print(f"Conjunto: {len(conjunto)} solicitudes ({suficientes} con información suficiente)\n")

    mediciones = [medir(conjunto, AjustesLLM(llm_proveedor="ninguno"), "reglas")]
    ajustes = AjustesLLM()
    if ajustes.llm_proveedor != "ninguno" and ajustes.clave:
        modo = f"LLM ({ajustes.llm_modelo})"
        mediciones.append(medir(conjunto, ajustes, modo, args.pausa))
    else:
        print("Sin GROQ_API_KEY: se mide solo el modo reglas.\n")
    imprimir(mediciones, args.detalle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
