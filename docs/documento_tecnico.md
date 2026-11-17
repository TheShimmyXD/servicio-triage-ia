# Servicio de triage de solicitudes

<p class="subtitulo">Documento técnico · Arquitectura, escalabilidad, estrategia de IA y despliegue en la nube</p>

## 1. Arquitectura propuesta

El servicio recibe una solicitud escrita en texto libre por cualquiera de las empresas clientes del BPO y se encarga de todo el triage: comprueba que traiga la información mínima, la clasifica, le asigna una prioridad, decide el próximo paso y, cuando la gestión es externa, crea el caso en la plataforma de esa empresa. Es un microservicio REST escrito en Python con FastAPI.

El código se organiza en cuatro capas (figura 1) y las dependencias van siempre en el mismo sentido: hacia el dominio, que concentra las reglas del negocio. Todo lo que cambia de una empresa a otra (categorías, prioridades, próximos pasos y plataforma) está en un archivo de configuración por empresa, no en el código.

<figure>
<svg viewBox="0 0 640 262" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Capas del servicio">
  <defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="punta"/></marker></defs>
  <rect class="caja config" x="4" y="4" width="306" height="30" rx="6"/>
  <text x="157" y="23" class="t">configuracion/empresas/*.yaml</text>
  <rect class="capa" x="4" y="50" width="132" height="108" rx="8"/><text x="12" y="64" class="capa-t">ENTRADA</text>
  <rect class="capa" x="170" y="50" width="140" height="108" rx="8"/><text x="178" y="64" class="capa-t">CASO DE USO</text>
  <rect class="capa" x="170" y="176" width="140" height="82" rx="8"/><text x="178" y="190" class="capa-t">DOMINIO</text>
  <rect class="capa" x="340" y="50" width="160" height="208" rx="8"/><text x="348" y="64" class="capa-t">ADAPTADORES</text>
  <text x="532" y="64" class="capa-t">SERVICIOS EXTERNOS</text>
  <rect class="caja" x="14" y="92" width="112" height="50" rx="6"/>
  <text x="70" y="114" class="t">entrypoints/api</text><text x="70" y="130" class="s">FastAPI · contrato</text>
  <rect class="caja fuerte" x="180" y="92" width="120" height="50" rx="6"/>
  <text x="240" y="114" class="t">app/triage</text><text x="240" y="130" class="s">caso de uso</text>
  <rect class="caja dominio" x="180" y="202" width="120" height="45" rx="6"/>
  <text x="240" y="222" class="t">domain</text><text x="240" y="237" class="s">reglas puras · puertos</text>
  <rect class="caja" x="350" y="74" width="140" height="44" rx="6"/>
  <text x="420" y="93" class="t">analizador_llm</text><text x="420" y="108" class="s">LLM o reglas</text>
  <rect class="caja" x="350" y="138" width="140" height="44" rx="6"/>
  <text x="420" y="157" class="t">proveedor_prioridad</text><text x="420" y="172" class="s">HTTP del cliente</text>
  <rect class="caja" x="350" y="202" width="140" height="44" rx="6"/>
  <text x="420" y="221" class="t">plataformas</text><text x="420" y="236" class="s">caso externo</text>
  <rect class="caja externo" x="530" y="74" width="100" height="44" rx="6"/><text x="580" y="100" class="t">Groq</text>
  <rect class="caja externo" x="530" y="138" width="100" height="44" rx="6"/><text x="580" y="164" class="t">Servicio MDV</text>
  <rect class="caja externo" x="530" y="202" width="100" height="44" rx="6"/><text x="580" y="228" class="t">Zendesk, Jira…</text>
  <path class="linea punteada" d="M270,34 V90" marker-end="url(#f)"/>
  <path class="linea" d="M126,117 H178" marker-end="url(#f)"/>
  <path class="linea" d="M240,142 V200" marker-end="url(#f)"/>
  <path class="linea" d="M300,105 C325,105 325,96 348,96" marker-end="url(#f)"/>
  <path class="linea" d="M300,117 C325,117 325,160 348,160" marker-end="url(#f)"/>
  <path class="linea" d="M300,129 C318,129 318,214 348,214" marker-end="url(#f)"/>
  <path class="linea punteada" d="M350,236 H302" marker-end="url(#f)"/>
  <path class="linea" d="M490,96 H528" marker-end="url(#f)"/>
  <path class="linea" d="M490,160 H528" marker-end="url(#f)"/>
  <path class="linea" d="M490,224 H528" marker-end="url(#f)"/>
</svg>
<figcaption>Figura 1. Las cuatro capas del servicio (bandas grises). Las flechas indican dependencia: la entrada llama al caso de uso; el caso de uso usa el dominio y los adaptadores; los adaptadores implementan los puertos del dominio (punteada) y son los únicos que alcanzan los servicios externos.</figcaption>
</figure>

Cada solicitud que llega al servicio (`POST /solicitudes`) sigue el recorrido de la figura 2.

<figure>
<svg viewBox="-4 0 708 136" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Flujo de una solicitud">
  <defs><marker id="h" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="punta"/></marker></defs>
  <rect class="caja" x="0" y="8" width="90" height="46" rx="6"/><text x="45" y="28" class="t">1. Validar</text><text x="45" y="43" class="s">entrada y empresa</text>
  <rect class="caja" x="122" y="8" width="90" height="46" rx="6"/><text x="167" y="28" class="t">2. Verificar</text><text x="167" y="43" class="s">datos mínimos</text>
  <rect class="caja" x="244" y="8" width="90" height="46" rx="6"/><text x="289" y="28" class="t">3. Clasificar</text><text x="289" y="43" class="s">LLM o reglas</text>
  <rect class="caja" x="366" y="8" width="90" height="46" rx="6"/><text x="411" y="28" class="t">4. Priorizar</text><text x="411" y="43" class="s">reglas o cliente</text>
  <rect class="caja" x="488" y="8" width="90" height="46" rx="6"/><text x="533" y="28" class="t">5. Decidir</text><text x="533" y="43" class="s">próximo paso</text>
  <rect class="caja fuerte" x="610" y="8" width="90" height="46" rx="6"/><text x="655" y="28" class="t">6. Crear caso</text><text x="655" y="43" class="s">en la plataforma</text>
  <path class="linea" d="M90,31 H120" marker-end="url(#h)"/>
  <path class="linea" d="M212,31 H242" marker-end="url(#h)"/>
  <path class="linea" d="M334,31 H364" marker-end="url(#h)"/>
  <path class="linea" d="M456,31 H486" marker-end="url(#h)"/>
  <path class="linea" d="M578,31 H608" marker-end="url(#h)"/>
  <rect class="caja externo" x="0" y="92" width="90" height="40" rx="6"/><text x="45" y="109" class="t">404 · 409 · 422</text><text x="45" y="123" class="s">error con código</text>
  <path class="linea punteada" d="M45,54 V90" marker-end="url(#h)"/><text x="49" y="76" class="s" style="text-anchor:start">no válida</text>
  <rect class="caja externo" x="122" y="92" width="90" height="40" rx="6"/><text x="167" y="109" class="t">Cierre</text><text x="167" y="123" class="s">info. insuficiente</text>
  <path class="linea punteada" d="M167,54 V90" marker-end="url(#h)"/><text x="171" y="76" class="s" style="text-anchor:start">falta</text>
  <rect class="caja externo" x="488" y="92" width="90" height="40" rx="6"/><text x="533" y="109" class="t">Respuesta</text><text x="533" y="123" class="s">directa · cerrado</text>
  <path class="linea punteada" d="M533,54 V90" marker-end="url(#h)"/><text x="537" y="76" class="s" style="text-anchor:start">directa</text>
  <rect class="caja dominio" x="610" y="92" width="90" height="40" rx="6"/><text x="655" y="109" class="t">pendiente + id</text><text x="655" y="123" class="s">o error_plataforma</text>
  <path class="linea" d="M655,54 V90" marker-end="url(#h)"/><text x="659" y="76" class="s" style="text-anchor:start">3 intentos</text>
</svg>
<figcaption>Figura 2. Flujo de una solicitud. Los datos mínimos son qué pasó, cuándo y qué necesita el cliente. El paso 5 decide el próximo paso y redacta la justificación; el 6 solo ocurre cuando la gestión es externa.</figcaption>
</figure>

## 2. Componentes y responsabilidades

La tabla sigue las carpetas del repositorio. Los *puertos* son las interfaces que el dominio define para todo lo que está afuera: el modelo de lenguaje, el servicio de prioridad del cliente, la plataforma de casos y el almacenamiento.

| Componente | Responsabilidad | Depende de |
|---|---|---|
| `domain/` | Las reglas del triage: contrato de entrada y salida, información mínima, prioridad, próximo paso, justificación, documento del cliente y duplicados. Define los cuatro puertos. | Nada: no usa red ni archivos. |
| `app/triage` | Orquesta el recorrido, reintenta la creación del caso, evita duplicados y lleva las métricas. | Solo el dominio y sus puertos. |
| `app/composicion` | Al arrancar, lee la configuración y conecta cada puerto con su adaptador. | Todas las capas (solo aquí). |
| `services/analizador_llm` | Pide al modelo la categoría, si la información alcanza y el documento del cliente. | Su puerto. |
| `services/proveedor_prioridad_http` | Consulta el servicio de prioridad de los clientes que tienen uno. | Su puerto. |
| `services/plataformas_simuladas` | Crea el caso en la plataforma de la empresa y devuelve su número. | Su puerto. |
| `services/repositorio_memoria` | Guarda cada solicitud atendida para reconocer los duplicados. | Su puerto. |
| `services/configuracion_empresas` | Carga y valida los archivos de las empresas; si uno tiene un error, el servicio no arranca y señala el archivo y el campo. | Pydantic y PyYAML. |
| `entrypoints/api` | Expone los endpoints y convierte los errores en respuestas HTTP. | `app/` y el contrato del dominio. |

### Qué está desacoplado y qué no

**Desacoplado.** El dominio no sabe nada de FastAPI, del proveedor del modelo ni de los archivos de configuración: recibe la configuración de la empresa ya validada y devuelve decisiones, por eso se prueba sin red. Los servicios externos entran siempre por un puerto, así que reemplazar uno consiste en escribir otro adaptador y registrarlo al arrancar, sin tocar el triage. El proveedor del modelo se cambia con variables de entorno y otra permite apagarlo y trabajar solo con reglas.

**Acoplado, a sabiendas.** Esta versión corre en un solo proceso, con tres consecuencias que la propuesta de nube (sección 6) resuelve:

- Las solicitudes atendidas y las métricas se guardan en memoria: se pierden al reiniciar y no se comparten entre réplicas. El almacenamiento ya está detrás de un puerto y las métricas viven en un único módulo, así que llevarlas a un servicio externo es un cambio localizado.
- Si llegan a la vez dos copias de la misma solicitud, un candado dentro del proceso las ordena. Con varias réplicas, esa garantía tiene que pasar a la base de datos.
- El caso se crea durante la misma petición: si la plataforma falla, quien llama espera los tres intentos. En producción, esa creación pasa a una cola.

Hay además límites menores: la configuración se lee al arrancar, así que un cambio exige reiniciar; la detección de la información mínima está pensada para textos en español, y conectar una plataforma real (no simulada) requiere programar su adaptador.

## 3. Por qué soporta el crecimiento en clientes y categorías

**Más empresas.** Incorporar una empresa es agregar su archivo de configuración con categorías, reglas de prioridad, próximos pasos y plataforma. El servicio lo valida al arrancar y, al reiniciarlo, la empresa queda disponible. Se comprobó con una quinta empresa ficticia, ACUEDUCTO DEL SUR, sin cambiar una línea de código.

**Más categorías y reglas.** Cada categoría se define en un solo lugar: el archivo de su empresa. Ahí tiene una descripción que orienta al modelo, palabras clave para el respaldo por reglas, su prioridad base y su próximo paso. La lista de categorías entre las que puede elegir el modelo se arma en cada petición a partir de ese archivo, de modo que una categoría nueva funciona en cuanto se escribe y no hay nada que reentrenar. Las señales de urgencia (frases como «urgente» o «varios días») solo pueden subir la prioridad, nunca bajarla.

**Prioridad propia del cliente.** Si una empresa tiene su propio servicio de prioridad, como MENSAJERIA DEL VALLE, basta con declarar en su archivo la dirección, el tiempo de espera y los reintentos. Si ese servicio no responde, la prioridad sale de las reglas y la justificación lo explica.

**Más volumen.** Aparte del almacenamiento y las métricas, que ya se pueden reemplazar, el servicio no guarda estado, así que crece agregando réplicas detrás de un balanceador. El punto más lento es la llamada al modelo: un tiempo máximo de espera (10 s por defecto) la acota y, si se agota, las reglas responden sin salir a la red.

## 4. Estrategia de IA y por qué

La estrategia es **híbrida**: el modelo de lenguaje interpreta el texto y las reglas de configuración toman las decisiones de negocio.

**Qué hace el modelo.** Lee la descripción y devuelve una respuesta estructurada que debe cumplir un esquema JSON estricto: la categoría (solo puede elegir entre las de la empresa), si la información es suficiente, los hechos de la solicitud y el tipo y número del documento del cliente. Se usa gpt-oss-20b, un modelo abierto servido por Groq, por su salida estricta, su velocidad y su bajo costo; cambiarlo es configuración.

**Por qué un modelo y no solo reglas.** Las solicitudes llegan en texto libre, con errores y muchas formas de decir lo mismo; un clasificador propio exigiría datos etiquetados y reentrenarlo con cada empresa nueva, mientras que el modelo recibe las categorías en cada petición. Sobre 32 solicitudes etiquetadas (8 por empresa, carpeta `evaluacion/`), el modelo acertó la categoría en 24 de 24 y el próximo paso en 32 de 32, con una mediana de 0,8 a 1 s en tres corridas; las reglas solas, en 11 de 24 y 12 de 32, porque ante la duda cierran por falta de información. Ese es el riesgo del respaldo: sin modelo, un caso válido puede cerrarse; el log marca la fuente de cada respuesta para revisarlo. El conjunto es pequeño y sintético: ampliarlo con casos reales es el paso siguiente.

**Por qué las decisiones no las toma el modelo.** La prioridad, el próximo paso y el estado salen de reglas porque forman parte del acuerdo con cada empresa: tienen que ser deterministas, auditables y repetibles, y no pueden depender de que un proveedor externo responda.

**Controles sobre la respuesta del modelo.**

- Toda respuesta se valida contra el esquema. Si el modelo no contesta, tarda o no cumple, resuelven las reglas de la empresa, se cuenta como falla en las métricas y la respuesta conserva su forma.
- El número de documento que propone el modelo solo se acepta si aparece en el texto original; si no, se extrae con reglas. Así, un número inventado nunca llega a la plataforma del cliente.

**En producción.** El texto de los clientes sale hacia el proveedor del modelo: conviene uno con acuerdo de tratamiento de datos o servido en la nube de la compañía, y enmascarar la cédula antes del envío (Ley 1581 de 2012), pues las reglas ya la extraen del texto. El adaptador sirve para cualquier API compatible con OpenAI.

## 5. Manejo de errores y monitoreo

| Situación | Qué hace el servicio |
|---|---|
| La plataforma de la empresa falla | Lo intenta tres veces (o las que fije el archivo de la empresa), esperando un poco más cada vez. Si no lo logra, responde igual con el triage completo, marca el estado como error de plataforma y explica el motivo en la justificación. Reenviar la solicitud vuelve a intentar la creación. |
| Solicitud repetida | Si el texto es el mismo, devuelve el resultado ya guardado sin consultar al modelo ni crear otro caso. Si el texto cambió, la rechaza (409). |
| La empresa no existe | Responde 404 con la lista de empresas válidas. |
| Falla el modelo | Resuelve con las reglas, con la misma forma de respuesta; tras tres fallas seguidas no lo llama durante 30 s. |
| El servicio de prioridad del cliente no responde | Reintenta según el archivo de la empresa y luego prioriza con las reglas, explicándolo en la justificación; tras tres consultas seguidas sin respuesta no lo llama durante 30 s (ambos valores, por empresa). |
| Entrada inválida o error imprevisto | Responde 422 indicando el campo y el problema; un error imprevisto devuelve 500 y queda en el log. |

Cada error trae un código legible (como `EMPRESA_NO_PARAMETRIZADA`) y un mensaje, descritos en el README.

Para el monitoreo, el servicio deja en el log cada intento fallido contra una plataforma (con la empresa, la solicitud y el número de intento), cada llamada al modelo con su latencia y sus tokens, y cada documento que el modelo propuso pero no aparecía en el texto. Además, el endpoint `/metricas` informa por empresa cuántos casos se crearon, cuántos intentos fallaron, cuántos casos no se pudieron crear, cuántos duplicados y conflictos hubo y cuántas veces falló el modelo, y `/salud` indica si el servicio está arriba. El repositorio incluye 160 pruebas automáticas, organizadas por capa y sin acceso a red.

## 6. Propuesta de despliegue en la nube

La propuesta usa AWS, aunque cada pieza tiene un equivalente directo en Azure o GCP: el servicio no depende de nada propio de un proveedor.

<figure>
<svg viewBox="0 0 640 184" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Despliegue en la nube">
  <defs><marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="punta"/></marker></defs>
  <rect class="caja config" x="240" y="2" width="130" height="30" rx="6"/><text x="305" y="21" class="s">Secrets Manager · S3 (YAML)</text>
  <rect class="caja externo" x="395" y="2" width="105" height="30" rx="6"/><text x="447" y="21" class="s">LLM (Bedrock / Groq)</text>
  <rect class="caja externo" x="5" y="67" width="80" height="44" rx="6"/><text x="45" y="87" class="t">BPO</text><text x="45" y="102" class="s">agentes</text>
  <rect class="caja" x="110" y="67" width="105" height="44" rx="6"/><text x="162" y="87" class="t">API Gateway</text><text x="162" y="102" class="s">WAF · cuotas</text>
  <rect class="caja fuerte" x="240" y="62" width="130" height="54" rx="6"/><text x="305" y="84" class="t">ECS Fargate</text><text x="305" y="100" class="s">N réplicas del servicio</text>
  <rect class="caja" x="395" y="67" width="105" height="44" rx="6"/><text x="447" y="87" class="t">SQS + DLQ</text><text x="447" y="102" class="s">creación de casos</text>
  <rect class="caja externo" x="525" y="67" width="110" height="44" rx="6"/><text x="580" y="87" class="t">Plataformas</text><text x="580" y="102" class="s">de cada empresa</text>
  <rect class="caja dominio" x="240" y="146" width="130" height="34" rx="6"/><text x="305" y="167" class="t">DynamoDB</text>
  <rect class="caja config" x="525" y="146" width="110" height="34" rx="6"/><text x="580" y="167" class="s">CloudWatch · X-Ray</text>
  <path class="linea" d="M85,89 H108" marker-end="url(#g)"/>
  <path class="linea" d="M215,89 H238" marker-end="url(#g)"/>
  <path class="linea" d="M370,89 H393" marker-end="url(#g)"/>
  <path class="linea" d="M500,89 H523" marker-end="url(#g)"/>
  <path class="linea" d="M305,116 V144" marker-end="url(#g)"/>
  <path class="linea punteada" d="M305,32 V60" marker-end="url(#g)"/>
  <path class="linea punteada" d="M355,62 C370,45 420,50 440,34" marker-end="url(#g)"/>
  <path class="linea punteada" d="M370,108 C450,125 480,160 523,163" marker-end="url(#g)"/>
</svg>
<figcaption>Figura 3. Despliegue propuesto. Las líneas punteadas son configuración, llamadas al modelo y telemetría.</figcaption>
</figure>

| Necesidad | Componente | Por qué |
|---|---|---|
| Ejecutar el servicio | Imagen de contenedor en **ECR**, ejecutada en **ECS Fargate** detrás de un **Application Load Balancer**, con autoescalado por CPU y por peticiones. | El servicio no guarda estado propio; Fargate evita administrar servidores y escala agregando réplicas. |
| Entrada pública | **API Gateway** con **WAF**, autenticación por empresa (llave de API o JWT) y cuotas por cliente. | Separa la seguridad y el control del tráfico del código; una empresa nueva recibe su llave sin desplegar nada. |
| Duplicados y estado | **DynamoDB**, con la empresa y el identificador de la solicitud como clave y escritura condicional. | Reemplaza el almacenamiento en memoria a través de su puerto y evita duplicados aunque haya varias réplicas. |
| Creación de casos | **SQS** con una cola aparte para los mensajes que fallan una y otra vez (DLQ), y un consumidor que llama a la plataforma de la empresa. | Quien llama recibe el triage al instante; los reintentos sobreviven a los reinicios y los casos que no se pudieron crear quedan a la vista para reprocesarlos. |
| Configuración de empresas | Archivos versionados en Git que el pipeline valida y publica en **S3** o **AppConfig**. | Una empresa o categoría nueva es un cambio de configuración revisado, no de código, y se puede revertir. |
| Secretos | **Secrets Manager** para la clave del modelo y las credenciales de cada plataforma. | La clave nunca queda en la imagen ni en el repositorio y se rota sin desplegar. |
| Modelo de lenguaje | **Amazon Bedrock**, o el proveedor actual a través de una salida controlada. | Mantiene los datos de los clientes dentro de la nube de la compañía cuando el contrato lo exige. |
| Observabilidad | **CloudWatch** para logs, métricas y alarmas (casos no creados, fallas del modelo, latencia) y **X-Ray** u OpenTelemetry para trazas. | Lo que el servicio ya registra y cuenta se convierte en tableros y alertas por empresa. |
| Entrega continua | **GitHub Actions**: revisa el estilo, corre las pruebas y valida la configuración; luego construye la imagen y la despliega en ECS de forma gradual. | Nada llega a producción sin pasar las mismas pruebas que se corren en local. |

Así, sumar una empresa es escribir su archivo y darle su llave en el gateway (y un adaptador solo si su plataforma es nueva); más volumen es sumar réplicas y consumidores. El código del triage no cambia.
