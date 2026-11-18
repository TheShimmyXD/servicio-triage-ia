<h1>Servicio de triage de solicitudes</h1>
<p class="tipo">Documento técnico de la prueba para Profesional Jr Analítica e IA</p>
<table class="ficha"><tr><td class="k">Autor</td><td>Andrés Moreno</td><td class="k">Fecha</td><td>18 de noviembre de 2026</td></tr><tr><td class="k">Repositorio</td><td><code>github.com/TheShimmyXD/servicio-triage-ia</code></td><td class="k">Versión</td><td>0.1.0</td></tr></table>

## 1. Arquitectura propuesta

El servicio recibe una solicitud escrita en texto libre por cualquiera de las empresas clientes del BPO y hace todo el triage: comprueba que traiga la información mínima, la clasifica, le asigna una prioridad, decide el próximo paso y, cuando la gestión es externa, crea el caso en la plataforma de esa empresa. Es un microservicio REST escrito en Python con FastAPI.

El código está en cuatro capas (figura 1) y las dependencias apuntan siempre hacia el dominio, que concentra las reglas del negocio. Lo que cambia de una empresa a otra (categorías, prioridades, próximos pasos y plataforma) vive en un archivo de configuración por empresa y no en el código.

<figure>
<svg viewBox="0 0 640 192" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Capas del servicio">
  <defs><marker id="f" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L10,5 L0,9 z" class="punta"/></marker></defs>
  <text x="10" y="12" class="col">Entrada (entrypoints/)</text>
  <text x="175" y="12" class="col">Aplicación (app/)</text>
  <text x="345" y="12" class="col">Adaptadores (services/)</text>
  <text x="530" y="12" class="col">Sistemas externos</text>
  <rect class="b" x="10" y="80" width="120" height="36"/><text x="70" y="96" class="m">entrypoints/api</text><text x="70" y="108" class="d">FastAPI y contrato</text>
  <rect class="b fuerte" x="175" y="80" width="120" height="36"/><text x="235" y="96" class="m">app/triage</text><text x="235" y="108" class="d">caso de uso</text>
  <rect class="b nucleo" x="175" y="150" width="120" height="36"/><text x="235" y="166" class="m">domain/</text><text x="235" y="178" class="d">reglas puras y puertos</text>
  <rect class="b" x="10" y="150" width="120" height="36"/><text x="70" y="166" class="m">configuracion/</text><text x="70" y="178" class="d">un YAML por empresa</text>
  <rect class="b" x="345" y="24" width="140" height="36"/><text x="415" y="40" class="m">analizador_llm</text><text x="415" y="52" class="d">LLM, con respaldo por reglas</text>
  <rect class="b" x="345" y="80" width="140" height="36"/><text x="415" y="96" class="m">proveedor_prioridad_http</text><text x="415" y="108" class="d">prioridad del cliente</text>
  <rect class="b" x="345" y="136" width="140" height="36"/><text x="415" y="152" class="m">plataformas_simuladas</text><text x="415" y="164" class="d">creación del caso</text>
  <rect class="ext" x="530" y="24" width="100" height="36"/><text x="580" y="40">Groq</text><text x="580" y="52" class="d">gpt-oss-20b</text>
  <rect class="ext" x="530" y="80" width="100" height="36"/><text x="580" y="96">Servicio de MDV</text><text x="580" y="108" class="d">prioridad propia</text>
  <rect class="ext" x="530" y="136" width="100" height="36"/><text x="580" y="152">Zendesk, Jira…</text><text x="580" y="164" class="d">de cada empresa</text>
  <path class="l" d="M130,98 H175" marker-end="url(#f)"/>
  <path class="l" d="M235,116 V150" marker-end="url(#f)"/>
  <path class="l" d="M295,98 H345" marker-end="url(#f)"/>
  <path class="l" d="M320,98 V42 H345" marker-end="url(#f)"/>
  <path class="l" d="M320,98 V154 H345" marker-end="url(#f)"/>
  <circle cx="320" cy="98" r="2" class="punta"/>
  <path class="l p" d="M130,168 H175" marker-end="url(#f)"/>
  <path class="l p" d="M345,166 H295" marker-end="url(#f)"/>
  <path class="l" d="M485,42 H530" marker-end="url(#f)"/>
  <path class="l" d="M485,98 H530" marker-end="url(#f)"/>
  <path class="l" d="M485,154 H530" marker-end="url(#f)"/>
</svg>
<figcaption><b>Figura 1.</b> Capas del servicio. Las flechas continuas son llamadas; las punteadas, la configuración ya validada que recibe el dominio y los puertos del dominio que implementan los adaptadores. Solo los adaptadores salen a la red.</figcaption>
</figure>

Cada solicitud que llega a `POST /solicitudes` sigue el recorrido de la figura 2.

<figure>
<svg viewBox="0 0 700 122" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Flujo de una solicitud">
  <defs><marker id="h" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L10,5 L0,9 z" class="punta"/></marker></defs>
  <rect class="b" x="1" y="4" width="96" height="36"/><text x="49" y="20">1. Validar</text><text x="49" y="32" class="d">entrada y empresa</text>
  <rect class="b" x="121" y="4" width="96" height="36"/><text x="169" y="20">2. Verificar</text><text x="169" y="32" class="d">datos mínimos</text>
  <rect class="b" x="241" y="4" width="96" height="36"/><text x="289" y="20">3. Clasificar</text><text x="289" y="32" class="d">LLM o reglas</text>
  <rect class="b" x="361" y="4" width="96" height="36"/><text x="409" y="20">4. Priorizar</text><text x="409" y="32" class="d">reglas o cliente</text>
  <rect class="b" x="481" y="4" width="96" height="36"/><text x="529" y="20">5. Decidir</text><text x="529" y="32" class="d">próximo paso</text>
  <rect class="b fuerte" x="601" y="4" width="96" height="36"/><text x="649" y="20">6. Crear caso</text><text x="649" y="32" class="d">en la plataforma</text>
  <path class="l" d="M97,22 H121" marker-end="url(#h)"/>
  <path class="l" d="M217,22 H241" marker-end="url(#h)"/>
  <path class="l" d="M337,22 H361" marker-end="url(#h)"/>
  <path class="l" d="M457,22 H481" marker-end="url(#h)"/>
  <path class="l" d="M577,22 H601" marker-end="url(#h)"/>
  <path class="l p" d="M49,40 V82" marker-end="url(#h)"/><text x="54" y="64" class="d izq">no válida</text>
  <path class="l p" d="M169,40 V82" marker-end="url(#h)"/><text x="174" y="64" class="d izq">falta un dato</text>
  <path class="l p" d="M529,40 V82" marker-end="url(#h)"/><text x="524" y="64" class="d" style="text-anchor:end">gestión directa</text>
  <path class="l" d="M649,40 V82" marker-end="url(#h)"/><text x="644" y="64" class="d" style="text-anchor:end">hasta 3 intentos</text>
  <rect class="ext" x="1" y="82" width="96" height="36"/><text x="49" y="98">Error HTTP</text><text x="49" y="110" class="d">404, 409 o 422</text>
  <rect class="ext" x="121" y="82" width="96" height="36"/><text x="169" y="98">Cierre</text><text x="169" y="110" class="d">info. insuficiente</text>
  <rect class="ext" x="481" y="82" width="96" height="36"/><text x="529" y="98">Respuesta directa</text><text x="529" y="110" class="d">estado cerrado</text>
  <rect class="b nucleo" x="601" y="82" width="96" height="36"/><text x="649" y="98">pendiente + id</text><text x="649" y="110" class="d">o error_plataforma</text>
</svg>
<figcaption><b>Figura 2.</b> Flujo de una solicitud. Los datos mínimos son qué pasó, cuándo y qué necesita el cliente. El paso 5 también redacta la justificación; el 6 solo ocurre cuando la gestión es externa.</figcaption>
</figure>

## 2. Componentes y responsabilidades

La tabla 1 sigue las carpetas del repositorio. Los *puertos* son las interfaces que el dominio define para todo lo que está afuera: el modelo de lenguaje, el servicio de prioridad del cliente, la plataforma de casos y el almacenamiento.

<p class="tabla"><b>Tabla 1.</b> Componentes, en el orden de las capas.</p>

| Componente | Responsabilidad | Depende de |
|---|---|---|
| `domain/` | Reglas del triage: contrato de entrada y salida, información mínima, prioridad, próximo paso, justificación, documento del cliente y duplicados. Define los cuatro puertos. | Nada; no usa red ni archivos. |
| `app/triage` | Orquesta el recorrido, reintenta la creación del caso, evita duplicados y lleva las métricas. | El dominio y sus puertos. |
| `app/composicion` | Al arrancar lee la configuración y conecta cada puerto con su adaptador. | Todas las capas (solo aquí). |
| `services/analizador_llm` | Pide al modelo la categoría, si la información alcanza y el documento del cliente. | Su puerto. |
| `services/proveedor_prioridad_http` | Consulta el servicio de prioridad de los clientes que tienen uno. | Su puerto. |
| `services/plataformas_simuladas` | Crea el caso en la plataforma de la empresa y devuelve su número. | Su puerto. |
| `services/repositorio_memoria` | Guarda cada solicitud atendida para reconocer duplicados. | Su puerto. |
| `services/configuracion_empresas` | Carga y valida los archivos de las empresas. Si uno tiene un error, el servicio no arranca y señala el archivo y el campo. | Pydantic y PyYAML. |
| `entrypoints/api` | Expone los endpoints y convierte los errores en respuestas HTTP. | `app/` y el contrato del dominio. |

### 2.1 Qué está desacoplado

El dominio no conoce FastAPI, ni al proveedor del modelo, ni los archivos de configuración. Recibe la configuración de la empresa ya validada y devuelve decisiones, y por eso se prueba sin red. Los servicios externos entran siempre por un puerto; reemplazar uno es escribir otro adaptador y registrarlo al arrancar, sin tocar el triage. El proveedor del modelo se cambia con variables de entorno, y otra variable lo apaga para trabajar solo con reglas.

### 2.2 Qué sigue acoplado

Esta versión corre en un solo proceso. Eso tiene tres consecuencias, que la propuesta de nube de la sección 6 resuelve:

- Las solicitudes atendidas y las métricas viven en memoria; se pierden al reiniciar y no se comparten entre réplicas. El almacenamiento ya está detrás de un puerto y las métricas en un único módulo, de modo que llevarlas afuera es un cambio localizado.
- Si llegan a la vez dos copias de la misma solicitud, un candado dentro del proceso las ordena. Con varias réplicas esa garantía tiene que pasar a la base de datos.
- El caso se crea dentro de la misma petición, así que si la plataforma falla, quien llama espera los tres intentos. En producción esa creación pasa a una cola.

Hay límites menores. La configuración se lee al arrancar y un cambio exige reiniciar; la detección de la información mínima está pensada para textos en español, y una plataforma real (no simulada) requiere programar su adaptador. Queda fuera del alcance el cierre por notificación de la empresa (paso 6): el caso queda `pendiente`, y el diseño previsto es un endpoint de resolución, o los eventos de la plataforma en la misma cola, que lo cierre con el motivo de su analista.

## 3. Crecimiento en clientes, categorías y volumen

<span class="corrido">Empresas nuevas.</span> Incorporar una empresa es agregar su archivo de configuración con categorías, reglas de prioridad, próximos pasos y plataforma. El servicio lo valida al arrancar y, al reiniciarlo, la empresa queda disponible. Lo probé con una quinta empresa ficticia, ACUEDUCTO DEL SUR, sin cambiar código.

<span class="corrido">Categorías y reglas.</span> Cada categoría se define en un solo lugar, el archivo de su empresa, con una descripción que orienta al modelo, palabras clave para el respaldo por reglas, su prioridad base y su próximo paso. La lista de categorías que puede elegir el modelo se arma en cada petición a partir de ese archivo, así que una categoría nueva funciona en cuanto se escribe y no hay nada que reentrenar. Las señales de urgencia («urgente», «varios días») solo pueden subir la prioridad.

<span class="corrido">Prioridad propia del cliente.</span> Si una empresa tiene su propio servicio de prioridad, como MENSAJERIA DEL VALLE, se declaran en su archivo la dirección, el tiempo de espera y los reintentos. Si ese servicio no responde, la prioridad sale de las reglas y la justificación lo dice.

<span class="corrido">Volumen.</span> Fuera del almacenamiento y las métricas, que ya se pueden reemplazar, el servicio no guarda estado y crece agregando réplicas detrás de un balanceador. El punto más lento es la llamada al modelo; un tiempo máximo de espera (10 s por defecto) la acota y, si se agota, responden las reglas sin salir a la red.

## 4. Estrategia de IA

La estrategia es híbrida. El modelo de lenguaje interpreta el texto y las reglas de configuración deciden.

### 4.1 Qué hace el modelo

Lee la descripción y devuelve una respuesta que debe cumplir un esquema JSON estricto: la categoría (solo entre las de la empresa), si la información es suficiente, los hechos de la solicitud y el tipo y número del documento del cliente. Uso gpt-oss-20b, un modelo abierto servido por Groq, por su salida estricta, su velocidad y su bajo costo; cambiarlo es configuración.

### 4.2 Por qué un modelo y no solo reglas

Las solicitudes llegan en texto libre, con errores y muchas formas de decir lo mismo. Un clasificador propio exigiría datos etiquetados y reentrenarse con cada empresa nueva, mientras que el modelo recibe las categorías en cada petición. La tabla 2 compara ambos sobre el conjunto de `evaluacion/`.

<p class="tabla"><b>Tabla 2.</b> Aciertos sobre 38 solicitudes etiquetadas (2 con inyección de instrucciones).</p>
<table class="cifras"><thead><tr><th>Clasificador</th><th>Categoría</th><th>Próximo paso</th><th>Mediana</th></tr></thead><tbody><tr><td>Modelo (gpt-oss-20b)</td><td>28 / 28</td><td>37 / 38</td><td>0,9 s</td></tr><tr><td>Solo reglas</td><td>10 / 28</td><td>21 / 38</td><td>sin red</td></tr></tbody></table>

El modelo falla un pedido vago que toma como trámite. Las reglas solas fallan más porque, ante la duda, cierran por falta de información; ese es el riesgo del respaldo, y por eso el log marca la fuente de cada respuesta. El conjunto es pequeño y sintético, y el paso siguiente es ampliarlo con casos reales.

### 4.3 Qué no decide el modelo

La prioridad, el próximo paso y el estado salen de reglas porque son parte del acuerdo con cada empresa. Tienen que ser deterministas y auditables, y no pueden depender de un proveedor externo. Sobre la respuesta del modelo hay tres controles:

- Toda respuesta se valida contra el esquema; si falla, resuelven las reglas y se cuenta en las métricas.
- El documento y el hecho citado solo se aceptan si aparecen en el texto, de modo que un dato inventado no llega al cliente.
- Un «suficiente» del modelo no abre un caso sin respaldo en el texto (qué pasó o un hecho citado). Así no lo abre un texto que le da órdenes al modelo; en vivo, 4 de 4 quedaron cerrados.

En producción, el texto de los clientes sale hacia el proveedor del modelo. Conviene uno con acuerdo de tratamiento de datos o servido en la nube de la compañía, y enmascarar la cédula antes del envío (Ley 1581 de 2012), cosa que las reglas ya pueden hacer porque la extraen del texto. El adaptador sirve para cualquier API compatible con OpenAI.

## 5. Manejo de errores y monitoreo

<p class="tabla"><b>Tabla 3.</b> Comportamiento ante cada falla.</p>

| Situación | Qué hace el servicio |
|---|---|
| Falla la plataforma de la empresa | Lo intenta tres veces (o las que fije el archivo de la empresa), esperando un poco más cada vez. Si no lo logra, responde igual con el triage completo, marca el estado como error de plataforma y explica el motivo en la justificación. Reenviar la solicitud vuelve a intentar la creación. |
| Solicitud repetida | Con el mismo texto devuelve el resultado guardado, sin consultar al modelo ni crear otro caso. Si el texto cambió, la rechaza con 409. |
| La empresa no existe | Responde 404 con la lista de empresas válidas. |
| Falla el modelo | Resuelve con las reglas y la misma forma de respuesta. Tras tres fallas seguidas deja de llamarlo durante 30 s. |
| No responde el servicio de prioridad del cliente | Reintenta según el archivo de la empresa y luego prioriza con las reglas, explicándolo en la justificación. Tras tres consultas seguidas sin respuesta deja de llamarlo durante 30 s (ambos valores, por empresa). |
| Entrada inválida o error imprevisto | Responde 422 con el campo y el problema; un error imprevisto devuelve 500 y queda en el log. |

Cada error trae un código legible (como `EMPRESA_NO_PARAMETRIZADA`) y un mensaje, descritos en el README.

Para el monitoreo, el log registra cada intento fallido contra una plataforma (empresa, solicitud y número de intento), cada llamada al modelo con su latencia y sus tokens, y cada documento que el modelo propuso pero no estaba en el texto. El endpoint `/metricas` informa, por empresa, los casos creados, los intentos fallidos, los casos que no se pudieron crear, los duplicados, los conflictos y las fallas del modelo; `/salud` indica si el servicio está arriba. El repositorio tiene 198 pruebas automáticas, organizadas por capa y sin acceso a red.

## 6. Propuesta de despliegue en la nube

La propuesta usa AWS; cada pieza tiene un equivalente directo en Azure o GCP.

<figure>
<svg viewBox="0 0 640 186" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Despliegue en la nube">
  <defs><marker id="g" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L10,5 L0,9 z" class="punta"/></marker></defs>
  <rect class="borde" x="92" y="2" width="436" height="182"/><text x="99" y="14" class="col">Cuenta de AWS</text>
  <rect class="ext" x="2" y="78" width="72" height="36"/><text x="38" y="94">Agentes</text><text x="38" y="106" class="d">del BPO</text>
  <rect class="b" x="104" y="78" width="96" height="36"/><text x="152" y="94">API Gateway</text><text x="152" y="106" class="d">WAF, llaves, cuotas</text>
  <rect class="b fuerte" x="222" y="72" width="128" height="48"/><text x="286" y="92">ECS Fargate (ALB)</text><text x="286" y="106" class="d">N réplicas del servicio</text>
  <rect class="b" x="205" y="24" width="78" height="28"/><text x="244" y="41" class="d">Secrets Manager</text>
  <rect class="b" x="290" y="24" width="78" height="28"/><text x="329" y="41" class="d">S3 / AppConfig</text>
  <rect class="b" x="392" y="24" width="122" height="28"/><text x="453" y="41" class="d">Bedrock u otro LLM</text>
  <rect class="b" x="374" y="78" width="66" height="36"/><text x="407" y="94">SQS</text><text x="407" y="106" class="d">con DLQ</text>
  <rect class="b" x="454" y="78" width="66" height="36"/><text x="487" y="94">Consumidor</text><text x="487" y="106" class="d">crea el caso</text>
  <rect class="ext" x="548" y="78" width="88" height="36"/><text x="592" y="94">Plataformas</text><text x="592" y="106" class="d">de cada empresa</text>
  <rect class="b nucleo" x="246" y="146" width="80" height="28"/><text x="286" y="163">DynamoDB</text>
  <rect class="b" x="374" y="146" width="146" height="28"/><text x="447" y="163" class="d">CloudWatch y X-Ray</text>
  <path class="l" d="M74,96 H104" marker-end="url(#g)"/>
  <path class="l" d="M200,96 H222" marker-end="url(#g)"/>
  <path class="l" d="M350,96 H374" marker-end="url(#g)"/>
  <path class="l" d="M440,96 H454" marker-end="url(#g)"/>
  <path class="l" d="M520,96 H548" marker-end="url(#g)"/>
  <path class="l" d="M286,120 V146" marker-end="url(#g)"/>
  <path class="l p" d="M244,52 V72" marker-end="url(#g)"/>
  <path class="l p" d="M329,52 V72" marker-end="url(#g)"/>
  <path class="l" d="M350,80 H360 V60 H453 V52" marker-end="url(#g)"/>
  <path class="l p" d="M350,112 H360 V160 H374" marker-end="url(#g)"/>
</svg>
<figcaption><b>Figura 3.</b> Despliegue propuesto. Las líneas punteadas son configuración y telemetría.</figcaption>
</figure>

<p class="tabla"><b>Tabla 4.</b> Componentes de la nube y su motivo.</p>

| Necesidad | Componente | Motivo |
|---|---|---|
| Ejecutar el servicio | Imagen en ECR, ejecutada en ECS Fargate detrás de un Application Load Balancer, con autoescalado por CPU y por peticiones. | El servicio no guarda estado propio; Fargate evita administrar servidores y escala agregando réplicas. |
| Entrada pública | API Gateway con WAF, autenticación por empresa (llave de API o JWT) y cuotas por cliente. | Saca la seguridad y el control del tráfico del código; una empresa nueva recibe su llave sin desplegar nada. |
| Duplicados y estado | DynamoDB, con la empresa y el identificador de la solicitud como clave y escritura condicional. | Reemplaza el almacenamiento en memoria a través de su puerto y evita duplicados aunque haya varias réplicas. |
| Creación de casos | SQS con una cola aparte para los mensajes que fallan una y otra vez (DLQ), y un consumidor que llama a la plataforma. | Quien llama recibe el triage al instante; los reintentos sobreviven a los reinicios y los casos no creados quedan a la vista para reprocesarlos. |
| Configuración de empresas | Archivos versionados en Git que el pipeline valida y publica en S3 o AppConfig. | Una empresa o categoría nueva es un cambio de configuración revisado, no de código, y se puede revertir. |
| Secretos | Secrets Manager para la clave del modelo y las credenciales de cada plataforma. | La clave no queda en la imagen ni en el repositorio y se rota sin desplegar. |
| Modelo de lenguaje | Amazon Bedrock, o el proveedor actual a través de una salida controlada. | Mantiene los datos de los clientes en la nube de la compañía cuando el contrato lo exige. |
| Observabilidad | CloudWatch para logs, métricas y alarmas (casos no creados, fallas del modelo, latencia); X-Ray u OpenTelemetry para trazas. | Lo que el servicio ya registra y cuenta se vuelve tableros y alertas por empresa. |
| Entrega continua | GitHub Actions revisa el estilo, corre las pruebas y valida la configuración; luego construye la imagen y la despliega en ECS de forma gradual. | Nada llega a producción sin pasar las mismas pruebas que se corren en local. |
