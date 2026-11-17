# Cambios

## [Sin publicar]

- Esqueleto del servicio: estructura por capas, configuración del proyecto y chequeo `GET /salud`.
- Dominio: contrato, documento del cliente, información mínima, prioridad, próximo paso y
  justificación.
- Configuración por empresa en YAML, validada al arrancar, con cuatro empresas.
- Caso de uso de triage con respaldo por reglas.
- API: `POST /solicitudes`, `GET /empresas` y errores con código (404, 409, 422, 500).
- Analizador LLM sobre Groq con salida JSON de esquema estricto y caída a reglas.
- Plataformas simuladas por registro, reintentos, `GET /metricas` y control de duplicados.
- Simulador del servicio de prioridad de MENSAJERIA DEL VALLE y su proveedor HTTP.
- README con instalación, variables, ejemplos, extensión, manejo de errores y supuestos.
- Documento técnico en `docs/` (PDF de 4 páginas) y su construcción desde Markdown.
- README con la URL del repositorio en las instrucciones de instalación.
- `Dockerfile` y `docker-compose.yml`: servicio de triage y simulador de MENSAJERIA DEL VALLE.
- GitHub Actions con `ruff` y `pytest` en cada cambio a `main`.
- Cortocircuito del servicio de prioridad de cada cliente, con `fallas_para_abrir` y `pausa_s`
  en su YAML.
- Tipos de documento en `configuracion/tipos_documento.yaml` y carpeta de empresas por
  `CARPETA_EMPRESAS`.
- Información mínima por categoría (`informacion_minima.por_categoria`) y cierre sin categoría.
- Las reglas controlan el "suficiente" del LLM: sin "qué pasó" ni un hecho copiado del texto,
  se cierra y se cuenta en `llm_suficiencia_no_respaldada`.
- Conjunto de evaluación con 38 solicitudes (consultas naturales e inyecciones) y cifras nuevas.
