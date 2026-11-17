# Imagen del servicio de triage. La misma imagen corre el simulador de prioridad de
# MENSAJERIA DEL VALLE (ver docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# El servicio ubica configuracion/empresas/ y .env relativo a su código, así que el árbol
# se copia completo y se instala en modo editable (las dependencias quedan en la imagen,
# el código se usa desde /app).
COPY . .
RUN pip install -e . \
    && useradd --no-create-home --uid 10001 servicio

# Sin privilegios de root en tiempo de ejecución.
USER servicio

EXPOSE 8000

CMD ["uvicorn", "entrypoints.api.principal:aplicacion", "--host", "0.0.0.0", "--port", "8000"]
