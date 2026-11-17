# Servicio de triage de solicitudes

[![Pruebas](https://github.com/TheShimmyXD/servicio-triage-ia/actions/workflows/pruebas.yml/badge.svg)](https://github.com/TheShimmyXD/servicio-triage-ia/actions/workflows/pruebas.yml)

Microservicio REST que recibe solicitudes en texto libre de varias empresas, las valida,
las clasifica, les asigna prioridad, decide el próximo paso y, cuando corresponde, crea el
caso en la plataforma de la empresa.

Cada empresa se describe en un archivo YAML (categorías, reglas de prioridad, delegaciones,
información mínima, plataforma y servicio de prioridad propio). Agregar una empresa o
cambiar sus reglas no toca el código.

## Qué hace

Por cada solicitud (`POST /solicitudes`):

1. **Valida la entrada** contra el contrato y busca la empresa en la configuración.
2. **Verifica la información mínima**: qué pasó, cuándo y qué necesita el cliente (cada
   empresa puede exigir menos). Si falta, cierra con `CIERRE_POR_INFORMACION_INSUFICIENTE`.
3. **Clasifica** en una de las categorías de la empresa y extrae el documento del cliente.
4. **Asigna prioridad** (Alta/Media/Baja) con las reglas de la empresa o, si la empresa lo
   tiene configurado, con su propio servicio de prioridad.
5. **Decide el próximo paso** según la delegación de la categoría: `GESTION_EXTERNA` o
   `RESPUESTA_DIRECTA`, y redacta la justificación.
6. **Crea el caso** en la plataforma de la empresa cuando el paso es `GESTION_EXTERNA` y
   devuelve su id ficticio (`ZD-000001`).

```
POST /solicitudes
      │
      ▼
 entrypoints/api ──► app/triage ──► domain (reglas puras: información mínima,
      ▲                  │                      prioridad, próximo paso, justificación)
      │                  ├──► services/analizador_llm ─────► Groq (o reglas si falla)
      │                  ├──► services/proveedor_prioridad ─► servicio del cliente (MDV)
      │                  └──► services/plataformas_simuladas ► id del caso externo
      └──── respuesta JSON del contrato
```

**Estrategia híbrida.** Un LLM (Groq, `openai/gpt-oss-20b`) lee el texto y responde con un
JSON de esquema estricto: categoría (solo las de la empresa), si la información es suficiente,
los hechos y el documento del cliente. Esa salida se valida; si el LLM no responde, se demora
o devuelve algo fuera del esquema, el mismo paso se resuelve con reglas por palabras clave del
YAML. La prioridad, el próximo paso y el estado nunca los decide el LLM: salen de reglas
configurables, que son auditables y repetibles.

### Estructura

| Carpeta | Qué contiene |
|---|---|
| `domain/` | Contrato, reglas del triage y puertos (interfaces). Sin red ni archivos. |
| `app/` | El caso de uso de triage, los reintentos, las métricas y el armado del servicio. |
| `services/` | Adaptadores: LLM, carga de los YAML, plataformas, servicio de prioridad, memoria. |
| `entrypoints/api/` | La API FastAPI y sus esquemas de entrada, salida y error. |
| `configuracion/empresas/` | Un YAML por empresa. |
| `simuladores/` | El servicio de prioridad de MENSAJERIA DEL VALLE, simulado. |
| `tests/` | Pruebas por capa, sin red. |
| `docs/` | Documento técnico (PDF) y su fuente en Markdown. |
| `Dockerfile`, `docker-compose.yml` | Imagen del servicio y los dos servicios juntos con Docker. |

## Requisitos e instalación

- Python 3.13 o superior.
- Una clave de Groq (gratuita en <https://console.groq.com/keys>). Sin clave el servicio
  funciona igual, solo con reglas.

En Linux o macOS:

```bash
git clone https://github.com/TheShimmyXD/servicio-triage-ia.git
cd servicio-triage-ia
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

En Windows (PowerShell). La política por defecto de Windows 11 no deja ejecutar
`Activate.ps1`, así que se llama directamente al Python del entorno:

```powershell
git clone https://github.com/TheShimmyXD/servicio-triage-ia.git
cd servicio-triage-ia
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env
```

Luego se abre `.env` y se completa `GROQ_API_KEY`. El `.env` no se versiona.

### Variables de entorno

Se leen del `.env` o del entorno (el entorno manda).

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `LLM_PROVEEDOR` | `groq` | `groq` usa el LLM; `ninguno` clasifica solo con las reglas de cada empresa. |
| `LLM_MODELO` | `openai/gpt-oss-20b` | Modelo del proveedor. Debe admitir salida JSON con esquema estricto. |
| `LLM_URL_BASE` | `https://api.groq.com/openai/v1` | URL base compatible con la API de OpenAI; permite cambiar de proveedor. |
| `GROQ_API_KEY` | vacía | Clave del proveedor. Vacía equivale a `LLM_PROVEEDOR=ninguno`. |
| `LLM_TIMEOUT_S` | `10` | Segundos de espera al LLM antes de resolver con reglas (máximo 60). |
| `PRIORIDAD_EXTERNA` | `activa` | `activa` consulta los servicios de prioridad de los clientes; `ninguna` usa siempre las reglas. |

La URL, el timeout y los reintentos de cada servicio de prioridad van en el YAML de su empresa.

## Cómo correrlo

Con el entorno activado, en dos terminales:

```bash
# Servicio de triage
uvicorn entrypoints.api.principal:aplicacion --port 8000

# Servicio de prioridad de MENSAJERIA DEL VALLE (simulado)
uvicorn simuladores.mensajeria_del_valle.servicio:aplicacion --port 8001
```

En Windows, las mismas órdenes con el Python del entorno:

```powershell
.venv\Scripts\python -m uvicorn entrypoints.api.principal:aplicacion --port 8000
.venv\Scripts\python -m uvicorn simuladores.mensajeria_del_valle.servicio:aplicacion --port 8001
```

El simulador es opcional: si no está arriba, MENSAJERIA DEL VALLE prioriza con sus reglas.
La documentación interactiva queda en <http://localhost:8000/docs>.

| Método y ruta | Qué devuelve |
|---|---|
| `POST /solicitudes` | El triage de una solicitud. |
| `GET /empresas` | Las empresas parametrizadas. |
| `GET /metricas` | Contadores por empresa: casos creados, fallas de plataforma, duplicados, LLM caído. |
| `GET /salud` | `{"estado": "ok"}`. |

### Con Docker

Sin instalar Python, `docker compose` levanta el servicio de triage y el simulador. El
simulador comparte la red del servicio de triage, así que la URL de su YAML no cambia.

```bash
cp .env.example .env   # opcional: sin clave clasifica solo con reglas
docker compose up --build
```

La clave se pasa al contenedor desde `.env` y no entra a la imagen. Los ejemplos de abajo
funcionan igual en `localhost:8000`; `docker compose down` detiene todo.

### Ejemplos

La solicitud del enunciado:

```bash
curl -s -X POST localhost:8000/solicitudes -H "Content-Type: application/json" -d '{
  "compania": "GASES DEL ORINOCO",
  "solicitud_id": "REQ-001",
  "solicitud_descripcion": "Mi nombre es Juana y mi numero de cédula es 102045678 . Solicito una revision urgente porque la estufa qué compre hace 2 semanas con la empresa presenta fallas (no está haciendo contacto con la llave del gas) "
}'
```

```json
{
  "compania": "GASES DEL ORINOCO",
  "solicitud_id": "REQ-001",
  "solicitud_fecha": "2026-11-17",
  "solicitud_tipo": "Incidente técnico",
  "solicitud_prioridad": "Alta",
  "solicitud_tipo_id_cliente": "CC",
  "solicitud_id_cliente": "102045678",
  "solicitud_id_plataforma_externa": "ZD-000001",
  "proximo_paso": "GESTION_EXTERNA",
  "justificacion": "Incidente técnico: \"Estufa comprada hace 2 semanas presenta fallas, no hace contacto con la llave del gas\". Prioridad Alta porque la solicitud menciona \"urgente\" (fuente: reglas de la empresa). Requiere gestión de la empresa (delegación externa).",
  "estado": "pendiente"
}
```

En Windows (PowerShell), la misma solicitud:

```powershell
$cuerpo = @{
  compania = "GASES DEL ORINOCO"
  solicitud_id = "REQ-001"
  solicitud_descripcion = "Mi nombre es Juana y mi numero de cédula es 102045678 . Solicito una revision urgente porque la estufa qué compre hace 2 semanas con la empresa presenta fallas (no está haciendo contacto con la llave del gas) "
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/solicitudes -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($cuerpo))
```

Una por empresa:

```bash
curl -s -X POST localhost:8000/solicitudes -H "Content-Type: application/json" -d '{"compania": "MENSAJERIA DEL VALLE", "solicitud_id": "MDV-001", "solicitud_descripcion": "Mi paquete no ha llegado y ya pasó una semana desde la fecha prometida, necesito saber qué pasó. Mi cédula es 1144556677"}'

curl -s -X POST localhost:8000/solicitudes -H "Content-Type: application/json" -d '{"compania": "RED MOVIL ANDINA", "solicitud_id": "RMA-001", "solicitud_descripcion": "Desde ayer no tengo señal ni datos en mi celular y necesito que lo revisen hoy. Mi cédula es 79888777"}'

curl -s -X POST localhost:8000/solicitudes -H "Content-Type: application/json" -d '{"compania": "SALUD INTEGRAL DEL LLANO", "solicitud_id": "SIL-001", "solicitud_descripcion": "Necesito agendar una cita de medicina general para la próxima semana. Mi documento es CC 1020304050"}'

curl -s -X POST localhost:8000/solicitudes -H "Content-Type: application/json" -d '{"compania": "GASES DEL ORINOCO", "solicitud_id": "REQ-002", "solicitud_descripcion": "Buenas tardes, quiero que me ayuden con lo de siempre por favor"}'
```

| Solicitud | Tipo | Prioridad | Próximo paso | Caso externo | Estado |
|---|---|---|---|---|---|
| MDV-001 | Envío retrasado | Alta (servicio del cliente) | `GESTION_EXTERNA` | `SF-000001` | `pendiente` |
| RMA-001 | Falla de servicio | Media | `GESTION_EXTERNA` | `FD-000001` | `pendiente` |
| SIL-001 | Cita médica | Baja | `RESPUESTA_DIRECTA` | `null` | `cerrado` |
| REQ-002 | `null` | `null` | `CIERRE_POR_INFORMACION_INSUFICIENTE` | `null` | `cerrado` |

## Cómo extenderlo

Todo se hace en `configuracion/empresas/`; el servicio valida los YAML al arrancar y no
arranca si alguno tiene un error (el mensaje dice el archivo y el campo).

**Agregar una empresa.** Crear un YAML nuevo y reiniciar el servicio. Ejemplo mínimo:

```yaml
nombre: ACUEDUCTO DEL SUR

categorias:
  - nombre: Falta de agua
    descripcion: El cliente no tiene servicio de agua o llega con muy poca presión.
    palabras_clave: [no tengo agua, sin agua, no llega el agua, baja presion]
  - nombre: Consulta de factura
    descripcion: Dudas sobre el valor, el consumo o la fecha de pago de la factura.
    palabras_clave: [factura, cobro, consumo, pago]

reglas_prioridad:
  por_defecto: Baja
  por_categoria:
    Falta de agua: Media
    Consulta de factura: Baja
  senales:
    - prioridad: Alta
      frases: [urgente, hospital, varios dias]

delegaciones:
  Falta de agua: GESTION_EXTERNA
  Consulta de factura: RESPUESTA_DIRECTA

plataforma:
  nombre: servicenow_simulada
  parametros:
    prefijo: SN
```

`GET /empresas` la lista de inmediato y sus casos salen como `SN-000001`. Opcionalmente,
`informacion_minima` define qué elementos exige y frases propias para detectarlos, y
`proveedor_prioridad` dice quién decide la prioridad (ver los YAML existentes).

**Agregar una categoría.** Sumarla a `categorias` (la descripción orienta al LLM y las
palabras clave al respaldo por reglas), darle prioridad en `reglas_prioridad.por_categoria`
y próximo paso en `delegaciones`.

**Cambiar las reglas de prioridad.** Editar `por_defecto`, `por_categoria` o `senales`: una
señal es una lista de frases que, si aparecen en el texto, suben la prioridad (nunca la
bajan de la base de la categoría).

**Integrar otra plataforma.** Para simularla basta con un nombre terminado en `_simulada` y
un prefijo. Para una real, se escribe un adaptador que cumpla `PlataformaCasos`
(`domain/puertos.py`: `crear_caso(caso) -> id`, y ante una falla lanza `ErrorPlataforma`) y se
registra por nombre en `REGISTRO` (`services/plataformas_simuladas.py`). El triage no cambia.

**Integrar el servicio de prioridad de un cliente.** Si el cliente expone el mismo contrato
que MENSAJERIA DEL VALLE (`tipo_documento`, `numero_documento_cliente`, `tipo_solicitud` →
prioridad), basta con el YAML:

```yaml
proveedor_prioridad:
  tipo: http
  url: http://127.0.0.1:8001/prioridad
  timeout_s: 2
  reintentos: 2
```

Un contrato distinto se resuelve con un adaptador que cumpla `ProveedorPrioridad`.

## Manejo de errores

**La plataforma externa falla.** Cada creación de caso se intenta 3 veces con espera
creciente (0,2 s y 0,4 s). Si todas fallan, la respuesta es 200 con
`"estado": "error_plataforma"`, el id externo en `null` y el motivo en la justificación:
el triage ya está hecho y no se pierde. Reenviar la misma solicitud vuelve a intentar la
creación. Para verlo, se agrega `fallas_iniciales: 3` en `parametros` de la plataforma de
una empresa (también existe `probabilidad_falla`, de 0 a 1) y se reinicia el servicio.

**Monitoreo.** Cada intento fallido queda en el log (`plataforma_fallo` y
`plataforma_agotada`, con empresa, plataforma, solicitud e intento) y en `GET /metricas`:

```json
{"casos_creados": {}, "intentos_fallidos_plataforma": {"GASES DEL ORINOCO": 3},
 "casos_no_creados": {"GASES DEL ORINOCO": 1}, "duplicados_devueltos": {},
 "conflictos_de_id": {}, "llm_fallidos": {}}
```

**Casos duplicados.** La clave es la empresa más el `solicitud_id`. Si llega de nuevo con el
mismo texto, se devuelve el resultado ya guardado sin llamar al LLM ni crear otro caso. Si
llega con otro texto, se rechaza con 409 `SOLICITUD_DUPLICADA`.

**Empresa no parametrizada.** 404 con `EMPRESA_NO_PARAMETRIZADA` y la lista de empresas
válidas. El nombre se compara sin distinguir mayúsculas, tildes ni espacios de más.

```json
{"codigo": "EMPRESA_NO_PARAMETRIZADA",
 "mensaje": "La empresa \"ACUEDUCTO DEL SUR\" no está parametrizada. Válidas: GASES DEL ORINOCO, MENSAJERIA DEL VALLE, RED MOVIL ANDINA, SALUD INTEGRAL DEL LLANO",
 "empresas_validas": ["GASES DEL ORINOCO", "MENSAJERIA DEL VALLE", "RED MOVIL ANDINA", "SALUD INTEGRAL DEL LLANO"]}
```

**El LLM no responde o responde mal.** La solicitud se resuelve con las reglas de la empresa
y se cuenta en `llm_fallidos`. El cliente recibe la misma forma de respuesta.

**El servicio de prioridad del cliente no responde.** Se reintenta según su YAML y luego se
prioriza con las reglas; la justificación dice por qué.

**Entrada inválida.** 422 `ENTRADA_INVALIDA` con el campo y el problema. Un error no
previsto devuelve 500 `ERROR_INTERNO` y queda en el log.

## Contrato

Entrada: `compania`, `solicitud_id` y `solicitud_descripcion` (texto de hasta 5000
caracteres). Salida: los campos del ejemplo del enunciado, en su orden.

El ejemplo de salida del enunciado tiene dos detalles que contradicen el resto del texto, y
la respuesta sigue al texto:

- En el ejemplo, `solicitud_tipo_id_cliente` trae el número y `solicitud_id_cliente` trae
  «CC». Aquí cada valor va en su campo: el tipo de documento (`"CC"`) en
  `solicitud_tipo_id_cliente` y el número en `solicitud_id_cliente`.
- `proximo_paso` usa los valores definidos en los requerimientos (`GESTION_EXTERNA`,
  `RESPUESTA_DIRECTA`, `CIERRE_POR_INFORMACION_INSUFICIENTE`) y `solicitud_fecha` va en
  minúscula como el resto de los campos.

### Supuestos

Lo que el enunciado no fija se resolvió así, y todo es configurable o está aislado en una
función del dominio:

- **Información mínima:** qué pasó, cuándo y qué necesita, detectados por marcadores del
  español más las frases de cada empresa. Un texto de menos de 5 palabras se cierra siempre.
  SALUD INTEGRAL DEL LLANO no exige «cuándo».
- **Documento:** CC (el del ejemplo), CE, NIT, TI y PA. Si hay varios, gana el primero.
- **Estado:** `pendiente` en `GESTION_EXTERNA`, `cerrado` en los otros dos pasos y
  `error_plataforma` si el caso no se pudo crear.
- **Prioridad:** base por categoría y la señal más fuerte del texto; una señal nunca la baja.
- **Justificación:** el hecho de la solicitud (sin números de documento), la prioridad con su
  motivo y su fuente, y el paso. En el cierre, «Información incompleta o faltante».
- **Empresas:** GASES DEL ORINOCO y MENSAJERIA DEL VALLE vienen del enunciado; RED MOVIL
  ANDINA y SALUD INTEGRAL DEL LLANO son ficticias, para mostrar reglas distintas. Las
  categorías, palabras clave y plataformas de todas son supuestas, salvo «Incidente
  técnico» de GASES DEL ORINOCO.
- **Servicio de MENSAJERIA DEL VALLE:** sus reglas son ficticias y distintas de las del
  triage, para que se note quién decidió la prioridad.

## Pruebas

```bash
pytest
ruff check .
```

En Windows: `.venv\Scripts\python -m pytest` y `.venv\Scripts\python -m ruff check .`

GitHub Actions corre lo mismo (`ruff check`, `ruff format --check` y `pytest`) en cada cambio a
`main`: `.github/workflows/pruebas.yml`.

134 pruebas, sin red: el LLM y los servicios de prioridad se reemplazan por dobles, y una
respuesta real de Groq guardada en `tests/fixtures/` comprueba el análisis de su formato.

| Carpeta | Qué cubre |
|---|---|
| `tests/domain/` | Contrato, documento del cliente, información mínima, prioridad, próximo paso, justificación y duplicados. |
| `tests/services/` | Carga y validación de los YAML, analizador del LLM (salidas válidas e inválidas), plataformas y proveedor HTTP. |
| `tests/app/` | El caso de uso completo, los reintentos y el armado del servicio. |
| `tests/entrypoints/` | La API: REQ-001, errores 404, 409 y 422, métricas. |
| `tests/simuladores/` | El servicio de prioridad de MENSAJERIA DEL VALLE. |

## Documento técnico

`docs/documento_tecnico.pdf` explica la arquitectura, cómo crece con más empresas y
categorías, la estrategia de IA, el manejo de errores y la propuesta de despliegue en la nube.
Su fuente es `docs/documento_tecnico.md`; para regenerarlo hace falta Chrome o Chromium (si no
está en el PATH, la variable `CHROME` indica la ruta del ejecutable):

```bash
pip install -e ".[docs]"
python docs/construir_pdf.py
```
