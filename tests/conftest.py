"""Ninguna prueba sale a la red: el LLM y los servicios de prioridad quedan apagados.

Se fija al importar (antes de recoger las pruebas) porque la API arma el caso de uso
cuando se importa su módulo. Las variables de entorno mandan sobre el .env.
"""

from __future__ import annotations

import os

os.environ["LLM_PROVEEDOR"] = "ninguno"
os.environ["PRIORIDAD_EXTERNA"] = "ninguna"
