# Preparación Estratégica — Entrevista Senior AI Engineer / Architect

> Este documento no es una guía de estudio. Es un arsenal de respuestas con opiniones formadas, defendibles y respaldadas por implementación real desde primeros principios. Cada respuesta refleja a alguien que **construyó** estos sistemas, no que leyó sobre ellos.

---

## Sección 1: Arquitectura de Agentes en Producción

### 1. **¿Cómo diseñarías un agent runtime para producción desde cero?**

Un agente de producción no es un `while True` con un LLM. Necesitás seis bloques arquitectónicos desacoplados: un **bucle ReAct** (Thought → Action → Observation → Decision) como motor de razonamiento, un **Event Bus** pub-sub para comunicación asíncrona entre componentes sin acoplamiento directo, un **Task Scheduler** para encolar ejecuciones de larga duración sin bloquear hilos HTTP, un **Memory Engine** con capas de corto plazo (ventana de conversación) y largo plazo (consolidación vectorial cross-session), un sistema de **Context Propagation** inspirado en OpenTelemetry que propague `trace_id`, `parent_span_id` y `tenant_id` a través de cada llamada anidada, y una capa de **Governance** transversal. Como se detalla en [Agent Runtime](./03_agent_runtime.md), la clave es que cada bloque sea testeable y reemplazable de forma independiente.

### 2. **¿ReAct loop o state machine? ¿Cuándo usar cada uno?**

Si el proceso es conocido, estable y tiene pasos claramente definidos, empiezo con una state machine o workflow explícito. Si el espacio de decisiones es abierto o impredecible, comienzo con un enfoque ReAct. La elección depende del nivel de incertidumbre del dominio.

**State Machine** (flujos deterministas):
- Onboarding de usuarios
- Procesamiento de facturas
- KYC y verificación de identidad
- Reclamos con pasos fijos

**ReAct** (espacio abierto):
- Investigación documental
- Soporte técnico complejo
- Análisis de documentos abiertos
- Asistentes internos con consultas impredecibles

En producción, la mayoría de los agentes customer-facing son ReAct porque las consultas son impredecibles. Los agentes de back-office suelen ser state machines con pasos fijos.

### 3. **¿ReAct puro, workflow puro o arquitectura híbrida?**

La mayoría de los sistemas modernos no utilizan agentes completamente autónomos ni workflows completamente deterministas.

Lo habitual es una **arquitectura híbrida**:

```
Workflow → LLM → Workflow → Tool → LLM → Workflow
```

El workflow controla el proceso global y los puntos críticos de negocio. Los LLMs se utilizan únicamente donde aportan razonamiento, clasificación o generación.

Frameworks como LangGraph, Temporal, Mastra y Gollem convergen hacia este modelo porque permite combinar autonomía con predictibilidad. La mayoría de los sistemas de producción que construyo actualmente siguen este enfoque.

### 4. **¿Cómo manejás el estado y la persistencia entre sesiones de un agente?**

Con un Memory Engine de dos capas. La memoria a corto plazo es la lista de mensajes de la conversación activa que se inyecta en la ventana de contexto. La memoria a largo plazo persiste cross-session: cuando el agente resuelve una tarea exitosamente, se ejecuta una **consolidación** que extrae una síntesis estructurada y la almacena en un índice (key-value o vectorial en pgvector). Al iniciar una nueva tarea, el runtime hace un **recall** no destructivo buscando experiencias pasadas por similitud semántica. Esto está implementado desde cero en [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py). Para checkpointing de estado intermedio en grafos complejos, LangGraph tiene soporte nativo de snapshots, pero si construís desde cero, serializás el estado del grafo en Postgres con un `agent_state JSONB` por `session_id`.

### 5. **¿Cómo diseñás la memoria de un agente?**

Diferencio cuatro capas que interactúan dinámicamente:

*   **Working Memory**: Contexto inmediato de la conversación — los mensajes actuales en la ventana de contexto.
*   **Episodic Memory**: Experiencias específicas pasadas — "la última vez que el usuario preguntó sobre X, la respuesta fue Y".
*   **Semantic Memory**: Conocimiento consolidado sobre usuarios y procesos — preferencias, patrones de comportamiento, reglas de negocio aprendidas.
*   **Procedural Memory**: Patrones de comportamiento y reglas aprendidas — cómo el agente resuelve ciertos tipos de problemas de forma recurrente.

**Implementación típica**: Postgres + pgvector para almacenamiento vectorial, extracción automática de memorias al final de cada conversación exitosa, ranking por relevancia semántica en el recall, y consolidación periódica que fusiona memorias episódicas en semánticas. Inspirado en enfoques como Mem0, Zep y Letta.

### 6. **¿Cómo manejás la concurrencia y las ejecuciones asíncronas de agentes?**

Con un **Event Bus** desacoplado y un **Task Scheduler**. El bus pub-sub permite que componentes como observabilidad y auditoría se suscriban a eventos (`tool_call_started`, `agent_completed`) sin modificar el código del agente. El scheduler encola ejecuciones de larga duración para procesarlas en background sin bloquear el request HTTP. En producción real, esto se traduce en Redis + Celery o BullMQ para colas de tareas, con SSE (Server-Sent Events) para mantener al cliente informado del progreso. Un agente que tarda 3 minutos no puede ejecutarse dentro del lifecycle de un request HTTP — necesitás colas, estado persistente y un mecanismo de notificación asíncrono.

### 7. **¿Cómo coordinás múltiples agentes?**

Existen varios patrones de coordinación:

*   **Supervisor Pattern**: Un agente coordinador distribuye tareas a agentes especializados. Es el más común y el que implemento por defecto.
*   **Planner / Executor**: Un agente planifica la estrategia, otro ejecuta las acciones. Útil cuando la planificación requiere razonamiento de alto nivel separado de la ejecución.
*   **Handoff**: Un agente transfiere el control a otro cuando detecta un dominio específico. Es el patrón que usa OpenAI Agents SDK nativamente.
*   **Event-Driven Agents**: Los agentes se comunican mediante eventos publicados en un bus compartido. Más desacoplado pero más complejo de depurar.

**Mi preferencia**: Comenzar con un único agente bien diseñado. Agregar coordinación multi-agente sólo cuando existe una necesidad clara de separación de responsabilidades. El error más común es sobre-ingenierizar con multi-agente cuando un solo agente con buenas tools resuelve el problema.

---

## Sección 2: Context Engineering (El Nuevo Paradigma)

### 8. **¿Qué es Context Engineering y por qué es el problema principal en 2026?**

**El mayor aprendizaje construyendo agentes fue que el problema principal no es el modelo sino el contexto.** Si controlás el contexto, controlás el comportamiento del agente. Context Engineering es el diseño sistemático de: qué información incluir, qué información excluir, cuándo recuperarla y cómo estructurarla o comprimirla.

En producción, enfrentamos tres problemas graves si simplemente alimentamos contexto de forma cruda:
*   **Lost in the Middle**: Los modelos suelen ignorar o diluir la relevancia de la información ubicada en el centro del contexto.
*   **Context Bloat**: Inyectar miles de tokens irrelevantes incrementa exponencialmente el costo, añade latencia y confunde el razonamiento del modelo.
*   **Retrieval Noise**: Fragmentos que contienen metadatos inútiles o textos repetitivos degradan la calidad de las respuestas.

### 9. **¿Cómo aprovechás ventanas de contexto grandes y evitás 'Lost in the Middle'?**

Los modelos modernos soportan millones de tokens en la ventana de contexto, pero inyectarlo todo es un error operativo y financiero. Aplico técnicas sistemáticas:
1.  **Retrieval Fusion**: Combinar resultados de múltiples retrievers (vectorial + BM25 full-text).
2.  **Reranking**: Uso un cross-encoder ligero (como BGE-Reranker o Cohere) para reordenar los resultados del retriever por relevancia real antes de inyectarlos.
3.  **Context Compression**: Algoritmos que detectan y eliminan palabras vacías o redundantes, o LLMs pequeños que extraen únicamente los hechos clave.
4.  **Ubicación Estratégica**: Posicionar la información más crítica y las instrucciones del comportamiento al principio y al final de la ventana de contexto, dejando la información secundaria en el medio para mitigar la degradación de atención del modelo.

### 10. **¿Cómo elegís qué modelo usar dinámicamente? (Model Routing)**

No todas las tareas requieren el modelo más costoso. Implemento **Model Routing** dinámico basado en la complejidad del flujo:
*   **Tareas Simples** (clasificación, formateo JSON, extracción rápida de entidades): Ruteo a modelos rápidos y ultra-baratos como `gemini-1.5-flash` o `gpt-4o-mini`.
*   **Tareas Complejas** (razonamiento multi-paso, generación crítica de código, planeación de bucles ReAct): Ruteo a modelos de frontera como `claude-3.5-sonnet` o `gpt-4o`.
*   **Implementación**: El runtime puede decidir mediante un clasificador de intención ligero (o un modelo local ligero de 7B) la complejidad del prompt del usuario y despachar la llamada al endpoint óptimo. Esto ahorra entre un 60% y un 80% en costos de API sin pérdida de rendimiento.

### 11. **¿Dónde ponés la lógica: prompt, tool o workflow?**

**Toda lógica determinista vive en código o en el workflow. El prompt sólo contiene instrucciones de comportamiento.** 
Cuanta más lógica crítica de negocio (como validación de campos, reglas de cálculo o flujos de decisiones) termine dentro del prompt, más difícil será testearla, versionarla y gobernarla de forma fiable.
*   **Workflows**: Orquestan los pasos deterministas y los flujos alternativos basados en lógica dura.
*   **Tools**: Ejecutan acciones directas con efectos secundarios (consultas SQL, integraciones API).
*   **Prompts**: Guían al modelo sobre el *tono*, el *estilo* y la *interpretación semántica* de la información contextualizada.

### 12. **¿Cómo evitás respuestas ambiguas? (Structured Outputs)**

Uso contratos estructurados. Nunca le pido al modelo que devuelva texto libre cuando necesito una estructura conocida. Le pido un contrato explícito.
*   **JSON Schema**: Definir el esquema exacto de la respuesta esperada.
*   **Pydantic**: Validación de tipos en Python con `output_type=MyModel`.
*   **Tool Calling**: El modelo "llama" una tool con parámetros tipados — es structured output nativo.
*   **Structured Outputs**: APIs nativas de OpenAI/Anthropic que garantizan conformidad con el schema.

**Beneficios**: Menos parsing, menos errores, integración más simple, mayor confiabilidad. Si el modelo no puede producir una respuesta válida según el schema, falla explícitamente en vez de devolver basura que rompe el pipeline downstream.

---

## Sección 3: RAG y Bases de Datos Vectoriales

### 13. **¿Por qué PostgreSQL + pgvector y no una base vectorial dedicada?**

Para la mayoría de los casos empresariales que he visto (decenas de miles o millones bajos de documentos), PostgreSQL + pgvector suele ser suficiente y ofrece una excelente relación entre simplicidad operativa y funcionalidad. Cuatro razones: 
1.  **Operación simplificada** — no configuro, aseguro ni pago por un clúster vectorial adicional. 
2.  **Consistencia ACID** — si un registro se actualiza o elimina, su vector también, sin retrasos de sincronización. 
3.  **Consultas híbridas** — un simple `JOIN` SQL o `WHERE` sobre metadatos relacionales (`tenant_id`, permisos) al mismo tiempo que la búsqueda por similitud coseno. 
4.  **Madurez** — décadas de optimización en backups, réplicas, HA y seguridad empresarial.

Cuando aparecen requerimientos avanzados de escalabilidad, búsquedas híbridas complejas, sparse vectors o distribución geográfica, considero motores especializados como Qdrant o Weaviate. Análisis completo en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 14. **¿Cómo funciona la similitud coseno y por qué se usa en RAG?**

La similitud coseno mide el ángulo entre dos vectores en el espacio multidimensional. Si apuntan en la misma dirección (ángulo 0°), el coseno es 1.0 (máxima similitud semántica). Si son perpendiculares (90°), es 0.0. La fórmula es el producto punto normalizado por las magnitudes: `cos(u,v) = (u·v) / (||u|| × ||v||)`. PostgreSQL pgvector usa la **distancia coseno** (1 - similitud) como métrica de error, donde valores cercanos a 0 indican alta similitud. Lo implementé desde cero en Python puro sin NumPy en [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py). La ventaja sobre la distancia euclidiana es que la coseno es invariante a la magnitud del vector — captura similitud semántica independientemente de la longitud del texto.

### 15. **¿Qué estrategia de chunking usás y por qué?**

Depende del dominio. **Sliding Window** (ventana de W palabras con overlap de O palabras) es simple, predecible y funciona bien para documentos técnicos estructurados. **Semantic Chunking** es superior para documentos narrativos o heterogéneos: divide en oraciones, calcula embeddings de cada una, y cuando la similitud coseno entre oraciones adyacentes cae debajo de un umbral (ej: 0.85), detecta un cambio de tema y cierra el bloque. La clave que pocos mencionan: el chunking no se optimiza por intuición, se optimiza midiendo **Hit Rate @ K** y **MRR @ K** contra un ground truth etiquetado. Si cambiás el tamaño de ventana y el MRR baja, volvés atrás. Implementación y métricas en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 16. **¿Qué es un índice HNSW y por qué es crítico en producción?**

HNSW (Hierarchical Navigable Small World) es un grafo multicapa de proximidad que permite búsquedas aproximadas de vecinos más cercanos (ANN) en tiempo logarítmico. En vez de comparar el query vector contra todos los vectores de la tabla (búsqueda exacta O(n)), HNSW navega capas del grafo saltando nodos hasta converger en los vecinos más cercanos. En Postgres se crea con `CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)`. Es crítico porque sin él, cada búsqueda semántica haría un scan completo de la tabla — con millones de chunks, la latencia sería inaceptable. Combinado con un índice GIN sobre metadatos JSONB, tenés búsquedas híbridas de alto rendimiento.

### 17. **¿Cuándo usarías Qdrant, LanceDB o DuckDB en lugar de pgvector?**

*   **Qdrant** (Rust): cuando tengo cientos de millones de vectores, necesito latencia sub-milisegundo, vectores dispersos (sparse), compresión de vectores o escalado en clústeres distribuidos nativos. 
*   **LanceDB** (Rust, serverless): para aplicaciones locales, notebooks Jupyter, herramientas embebidas o entornos cloud donde no quiero pagar un servidor inactivo — es como SQLite pero para vectores, con formato columnar Lance optimizado para datos multimodales. 
*   **DuckDB**: no es base vectorial pura, sino motor OLAP embebido — lo uso para procesar eval datasets de RAG, analizar logs masivos de observabilidad o hacer cómputos de recuperación sobre tablas temporales en memoria. Análisis comparativo completo de 7 motores en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 18. **¿Cómo evaluás la calidad de un retriever en RAG?**

Con dos métricas fundamentales contra un ground truth etiquetado:
*   **Hit Rate @ K**: porcentaje de consultas de prueba en las que el documento correcto (ground truth) está presente entre los primeros K resultados del retriever.
*   **MRR @ K (Mean Reciprocal Rank)**: pondera el recíproco de la posición del acierto. Si el documento esperado es el 1° suma 1.0, si es el 2° suma 0.5, si es el 3° suma 0.33.

El MRR es más informativo que el Hit Rate porque premia al sistema por poner las respuestas correctas en primer lugar. Iteramos ajustando tamaño de chunk, overlap, modelos de embedding y pesajes en búsquedas híbridas hasta maximizar el MRR.

---

## Sección 4: Human-in-the-Loop y Transformación de IA Cross-Org

### 19. **¿Cómo identificás qué procesos de una organización automatizar primero con IA?**

Con un framework de tres ejes: **volumen** (¿cuántas veces se ejecuta por día/semana?), **valor cognitivo** (¿es repetitivo y de bajo juicio humano?) y **costo de error** (¿qué pasa si el agente se equivoca?). Los procesos de alto volumen, bajo valor cognitivo y bajo costo de error son los primeros candidatos. Ejemplo típico: clasificación de tickets de soporte, extracción de datos de facturas, generación de resúmenes de reuniones. Los procesos de alto juicio o alto costo de error (decisiones legales, aprobación de créditos) requieren human-in-the-loop. La trampa es empezar por lo "cool" en vez de lo que genera ROI medible.

### 20. **¿Cuándo incorporás Human-in-the-Loop (HITL) en un flujo de agentes?**

Incorporo la revisión humana de manera explícita cuando se cumplen ciertas condiciones críticas:
*   **Alto costo de error**: Operaciones financieras, cambios normativos de compliance o envío de información legalmente vinculante.
*   **Baja confianza en la predicción**: El score de confianza o certidumbre arrojado por el modelo cae por debajo de un umbral establecido.
*   **Acciones irreversibles**: Modificaciones destructivas en producción, cancelación de cuentas de clientes o transferencias monetarias.

El patrón arquitectónico sigue este flujo:

```
                  [Confidence >= Threshold]
Agent Execution ─────────────────────────────► Auto-Execute
      │
      │ [Confidence < Threshold]
      ▼
Human Review Queue ──► [Human Approval] ──► Execute & Log
      │
      ▼ [Correction / Rejection]
Save to Fine-Tuning Dataset (Agent Learns)
```

Este esquema asegura que los datos generados a partir de correcciones humanas alimenten directamente nuestro framework de evaluación y el dataset de fine-tuning para mejorar el comportamiento del agente con el tiempo.

### 21. **¿Qué es el flywheel de la "self-improving company"?**

Es el ciclo de retroalimentación donde cada proceso automatizado libera capacidad humana y genera datos que alimentan la siguiente automatización. El agente que clasifica tickets genera datos etiquetados que mejoran el modelo de clasificación. El agente que resume reuniones genera contexto que el agente de project management consume. Cada automatización exitosa reduce el costo marginal de la siguiente. El rol del arquitecto es diseñar la **arquitectura de datos transversal** que permita este flujo: telemetría de agentes → eval datasets → fine-tuning → mejor agente → más telemetría. Como se detalla en [Introducción](./00_introduccion.md), el verdadero impacto de la IA no es construir demos, es crear sistemas organizacionales que aprenden.

### 22. **¿Cómo comunicás decisiones técnicas de IA a stakeholders no técnicos?**

Traduciendo complejidad técnica a impacto de negocio.
*   En vez de *"necesitamos un índice HNSW para optimizar la búsqueda ANN"*, digo *"hoy el equipo de ventas tarda 15 minutos en encontrar información de un cliente; con este cambio, va a tardar 10 segundos"*.
*   En vez de *"el F1 score del retriever es 0.72"*, digo *"de cada 10 respuestas que da el asistente, 7 son correctas y 3 necesitan revisión humana — vamos a subirlo a 9 de 10 en el próximo sprint"*.

Parte del trabajo del arquitecto es traducir complejidad técnica a impacto de negocio.

### 23. **¿Cómo priorizás iniciativas de IA cuando todo el mundo quiere "su" agente?**

Con una matriz de impacto vs. complejidad y un roadmap visible para toda la organización. Cada iniciativa se puntúa en: (1) horas-hombre ahorradas por mes, (2) complejidad técnica (¿tenemos los datos? ¿el proceso está documentado?), (3) dependencia de otras iniciativas. Las de alto impacto y baja complejidad van primero. Las de alto impacto y alta complejidad se planifican para el trimestre siguiente. Las de bajo impacto se descartan explícitamente — decir "no" es parte del trabajo del arquitecto. El error más común es construir agentes para todos los departamentos en paralelo sin terminar ninguno. Mejor un agente en producción que diez en demo.

### 24. **¿Cómo manejás el cambio cultural cuando introducís IA en un equipo que tiene miedo de ser reemplazado?**

Posicionando la IA como amplificador, no como reemplazo. El framing correcto es: "el agente se encarga de las 4 horas de trabajo repetitivo para que vos puedas dedicar esas 4 horas al trabajo estratégico que solo vos podés hacer". En la práctica, involucro a los domain experts desde el día uno en el diseño del agente — ellos definen los criterios de éxito, etiquetan el ground truth y validan las salidas. Cuando el equipo siente que el agente es "suyo" y no algo que "les imponen", la adopción se acelera. También es crítico tener un período de shadow mode donde el agente sugiere pero no ejecuta, para generar confianza gradual.

---

## Sección 5: Observabilidad, Evaluación y Gobernanza

### 25. **¿Cómo depurás un agente en producción y por qué OpenTelemetry es tu estándar?**

Mi objetivo arquitectónico es que toda la telemetría de agentes termine en **OpenTelemetry (OTel)** como estándar común de la industria. OTel me permite exportar traces y métricas a cualquier backend compatible (como LangFuse, LangSmith, Datadog, SigNoz o Dynatrace) sin lock-in tecnológico.

Cada ejecución del agente genera un `trace_id` único que se propaga a todas las llamadas anidadas (queries vectoriales, llamadas al gateway de IA, invocaciones a herramientas). La traza de OTel genera un árbol jerárquico de spans donde registro:
*   Tipo de span (e.g., `llm_call`, `tool_execution`, `vector_search`).
*   Metadatos clave (e.g., modelo, tokens, latencia, versión de prompt).
*   Eventos y logs específicos de error.

Cuando el agente da una respuesta errática, ubico el `trace_id` y veo exactamente qué componente falló: si el retriever inyectó ruido, si la tool devolvió datos incompletos o si el LLM falló al razonar a pesar de tener el contexto correcto. Detallado en [Observabilidad y Evals](./04_observability_and_evals.md).

### 26. **¿Qué métricas de evaluación usás para medir la calidad de un agente?**

Tres niveles según el tipo de output:
*   **Exact Match**: Para respuestas deterministas (clasificación, extracción de campos): 1.0 si coincide exactamente, 0.0 si no.
*   **F1 Token Overlap**: Para respuestas generativas de longitud media (resúmenes, respuestas RAG): mide precision y recall a nivel de tokens de palabras, tolerando variaciones sintácticas.
*   **G-Eval (LLM como juez)**: Para outputs complejos o conversacionales (empatía, tono de voz) donde las métricas de strings fallan. Un LLM avanzado (GPT-4o) evalúa contra criterios definidos y puntúa del 1 al 5 justificando su respuesta.

Además, uso **Pairwise Evaluation** en despliegues A/B y muestreo periódico de evaluación humana. Guardamos y versionamos estos datasets de evaluación en Git junto con los prompts para garantizar que cambios sutiles no causen regresiones.

### 27. **¿Qué es el versionado de prompts y por qué es crítico?**

Un cambio de un adjetivo en el system prompt o una modificación en la firma de una tool puede desencadenar fallos en cascada. Los prompts no deben tratarse como configuración en base de datos que se actualiza sin control — deben gobernarse bajo el ciclo de vida del software estándar. Una versión del sistema (ej: `v1.2.0`) debe garantizar un estado fijo de: la plantilla del prompt, la versión del modelo (`gemini-1.5-flash-001` vs `002`), los hiperparámetros (temperatura, top-p) y la firma de las tools asociadas. Cada span de observabilidad debe inyectar metadatos con `prompt_version` y `agent_tag` para correlacionar caídas de rendimiento con cambios específicos en Git. Detallado en [Observabilidad y Evals](./04_observability_and_evals.md).

### 28. **¿Cómo implementás gobernanza de seguridad en un sistema de agentes?**

Con el principio fundamental: **la seguridad de un agente es un problema de ingeniería de sistemas, no un truco de redacción de prompts**. Nunca confío en que el modelo respete instrucciones de seguridad — un atacante con prompt injection puede anularlas. Implemento un `ToolGater` (patrón Wrapper, inspirado en el Agent Governance Toolkit de Microsoft) que intercepta cada llamada a herramienta y valida cinco capas antes de ejecutar: (1) **Kill Switch** — interruptor global de emergencia, (2) **RBAC** — rol del agente vs. permisos requeridos por la tool, (3) **Budget Gate** — costo acumulado vs. límite diario, (4) **Rate Limiting** — ventana deslizable de llamadas por minuto, (5) **PII Masking** — regex para emails y teléfonos que se redactan antes de enviar al LLM. Implementación completa en [Gobernanza y Seguridad](./05_governance_and_security.md).

### 29. **¿Qué es un kill switch y cuándo lo usarías?**

Un kill switch es un interruptor global de emergencia que, al activarse, cancela la ejecución de **cualquier** herramienta del sistema de forma inmediata. Se usa cuando detectás comportamiento anómalo en producción: un agente que entra en bucle infinito, un patrón de llamadas sospechoso, o una vulnerabilidad de seguridad descubierta. La diferencia con simplemente "apagar el servidor" es que el kill switch es granular y reversible — lo activás desde un dashboard, aislás el problema, y lo desactivás cuando está resuelto, sin downtime del resto del sistema. Es el último recurso de la capa de gobernanza y debe existir desde el día uno en producción.

### 30. **¿Cómo monitoreás y controlás costos financieros en tiempo real?**

El **CostTracker** utiliza los **usage metrics reales** reportados por cada proveedor como fuente de verdad definitiva para observabilidad y facturación. Las estimaciones previas de tokens (ej: `caracteres // 4`) se utilizan únicamente para predicción de costos y aplicación de budget gates preventivos.

El flujo de control consta de tres fases:
1.  **Cálculo Asíncrono e Incremental**: El `CostTracker` consume los campos `usage` directos del payload de respuesta del LLM (tokens de entrada y salida) y los multiplica por las tarifas por millón de tokens específicas del modelo.
2.  **Budget Gate Acumulativo**: El runtime mantiene el costo diario acumulado por sesión, proyecto y usuario en una base de datos distribuida en memoria (Redis). Si el costo total del día excede un límite configurado (ej: $1.00 USD), el `ToolGater` deniega llamadas subsiguientes.
3.  **Rate Limiter de Ventana Deslizable**: Limita las llamadas máximas por minuto para atajar bucles de ejecución infinita del bucle ReAct antes de que disparen los costos drásticamente.

Esta instrumentación previene facturas sorpresa ante excepciones mal controladas en bucles autónomos.

---

## Sección 6: Estrategia, Model Lifecycle y Build vs Buy

### 31. **¿Cuándo construís desde cero y cuándo adoptás un framework?**

Tres criterios claros. **Construyo desde cero** cuando el producto core de IA es el diferenciador del negocio y necesito control total sobre latencia, costos y seguridad — la depuración toma minutos, no horas, y no tengo dependency hell. **Adopto un framework ligero** (PydanticAI, Mastra) cuando necesito tipado estático estricto y velocidad de desarrollo sin la sobrecarga de LangChain. **Adopto LangGraph/LangChain** cuando estoy en un entorno corporativo que ya usa su ecosistema (LangSmith, LangServe) y necesito integrar decenas de APIs rápido. La decisión se evalúa bajo el prisma del mantenimiento a largo plazo, no de la velocidad inicial. Matriz completa en [Ecosistema de Frameworks](./06_framework_ecosystem.md).

### 32. **¿Cuál es la "complexity tax" de LangChain y cuándo vale la pena pagarla?**

LangChain introdujo abstracciones pesadas (LCEL, chains, agents) que dificultan la depuración — las excepciones suelen estar enterradas bajo docenas de clases abstractas. Los breaking changes entre versiones son frecuentes y requieren refactorizaciones constantes. La dependency chain es profunda. **Vale la pena** cuando: (1) ya estás invertido en LangSmith para observabilidad corporativa, (2) necesitás integrar muchas APIs rápido con sus conectores pre-construidos, (3) el equipo ya conoce la sintaxis. **No vale la pena** cuando: (1) tu producto es el agente en sí mismo y necesitás control total, (2) tu stack es TypeScript (Mastra es mejor opción), (3) tenés un equipo pequeño que se beneficia más de entender el código que de abstraerlo.

### 33. **¿Cómo evaluás un framework nuevo?**

Con cinco preguntas críticas de mantenimiento a largo plazo:
1.  **¿Resuelve problemas reales o es un wrapper redundante?**: Si solo envuelve APIs HTTP de OpenAI o Anthropic añadiendo sintaxis propietaria, es ruido.
2.  **Costo de salida (Lock-in)**: ¿Qué tan acoplado queda mi código de dominio al framework si tengo que reemplazarlo por primitivas propias?
3.  **Soporte de estándares industriales**: ¿Soporta protocolos abiertos como MCP (Model Context Protocol) o exportación a OpenTelemetry?
4.  **Madurez y actividad**: Commits recientes, issues abiertos y tamaño de la comunidad activa.
5.  **Tipado y DX**: ¿Tiene soporte estricto de TypeScript o Pydantic para autocompletado y validación de tipos durante el desarrollo?

### 34. **¿Qué es MCP (Model Context Protocol) y por qué es relevante como estándar de interoperabilidad?**

MCP es un protocolo cliente-servidor abierto creado por Anthropic que estandariza cómo los LLMs exponen tools y consumen datos contextuales de diferentes fuentes. En lugar de escribir un wrapper custom para que cada agente lea de Postgres, use Slack o consulte Jira, MCP desacopla las herramientas del runtime.
*   **Servidores MCP**: Exponen los recursos, herramientas y prompts con esquemas unificados.
*   **Clientes MCP** (nuestro Agent Runtime): Consumen las herramientas declaradas en el servidor independientemente del framework utilizado.

MCP tiene el potencial de ser el "REST" para el ecosistema de agentes, permitiendo que compartamos catálogos enteros de herramientas entre diferentes equipos u organizaciones sin duplicación de código.

### 35. **¿Fine-tuning o RAG? ¿Cómo diseñás el roadmap de optimización de un modelo?**

Uso un enfoque pragmático y económico de optimización progresiva:

```
Prompting ──► RAG ──► Structured Outputs ──► Tool Use ──► Fine-Tuning ──► Distillation
```

La gran mayoría de las organizaciones no necesitan saltar de inmediato a entrenar o afinar modelos. El fine-tuning tradicional y la destilación se justifican únicamente cuando las etapas previas han alcanzado sus límites físicos de rendimiento:
*   **RAG + Structured Outputs**: Resuelve el 90% de los casos de conocimiento dinámico e integración corporativa con latencias y costos razonables.
*   **Fine-Tuning**: Lo uso para forzar formatos específicos (JSON complejos de baja varianza), adaptar tonos de voz corporativos profundos, o entrenar modelos pequeños y locales en un dominio extremadamente de nicho.
*   **Distillation**: Para reducir costos drásticamente en producción de alta escala.

### 36. **¿Cómo funciona Model Distillation y cuándo lo implementás para optimizar costos?**

**Model Distillation** es la técnica clave en 2026 para escalar arquitecturas financieramente eficientes. Consiste en transferir la capacidad de razonamiento de un modelo grande y costoso (modelo maestro, e.g., GPT-4o, Claude 3.5 Sonnet) a un modelo pequeño y económico (modelo estudiante, e.g., Qwen 2.5 7B, Llama 3 8B).

El pipeline que implemento es:
1.  **Evaluación**: Ejecuto la tarea crítica usando el modelo maestro sobre un set representativo de consultas.
2.  **Dataset Generation**: Almaceno los pares input-output exitosos (verificados por e-vals y jueces LLM) para construir un dataset de entrenamiento limpio de miles de registros.
3.  **Entrenamiento (Fine-Tuning)**: Ajusto el modelo pequeño de código abierto (Qwen/Llama) con este dataset de outputs destilados.
4.  **Local Deployment**: Corro el modelo destilado localmente (vía vLLM/Ollama en Kubernetes) o mediante endpoints serverless. El modelo pequeño alcanza un accuracy similar al modelo de frontera para esa tarea específica, reduciendo los costos de tokens en más del 95%.

---

## Sección 7: AI Platform Architecture: cómo escalar de 1 agente a 1000 agentes en una organización

### 37. **¿Cómo diseñarías una plataforma interna para que 20 equipos creen 200 agentes sin caos?**

Cuando una organización escala su estrategia de IA, no puede permitir que cada equipo cree un runtime propio, use llaves de API individuales u optimice prompts de forma aislada. Se diseña una **AI Platform** centralizada que actúe como middleware común:

```
Equipos de Desarrollo (App 1, App 2, ...)
       │
       ▼ (pip install internal-agent-sdk)
┌─────────────────────────────────────────────────────────────────────────┐
│ AI Platform Architecture (Shared Service Layer)                         │
│                                                                         │
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────┐  │
│  │    Common Runtime     │ │     Tool Registry     │ │Prompt Registry│  │
│  └───────────────────────┘ └───────────────────────┘ └───────────────┘  │
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────┐  │
│  │ Evaluation Platform   │ │  Unified Observability│ │ Shared Memory │  │
│  └───────────────────────┘ └───────────────────────┘ └───────────────┘  │
│  ┌───────────────────────┐                                              │
│  │      AI Gateway       │ (Caching, Cost Attribution, Multi-tenancy)   │
│  └──────────┬────────────┘                                              │
└─────────────┼───────────────────────────────────────────────────────────┘
              ▼
    External API Providers (OpenAI, Gemini, Anthropic, Local vLLM)
```

La plataforma consta de los siguientes pilares de software:
*   **Common Runtime**: SDK interno (`pip install agent-platform-sdk`) que provee una clase base `Agent` común. Contiene hooks para logging, inyección de memoria y manejo del estado.
*   **Tool Registry**: Catálogo centralizado e interoperable (basado en MCP) de herramientas comunes seguras. Los equipos no escriben su propia herramienta para leer una DB de clientes; la importan del catálogo ya validado, securizado y con rate limits.
*   **Prompt Registry**: Sistema versionado de plantillas de prompts sincronizado con Git. Esto permite rastrear qué prompt está en producción y prevenir regresiones por cambios sutiles.
*   **Evaluation Platform (CI/CD)**: Pipeline automatizado donde cada cambio en un prompt o código de agente corre un set de evals sobre datasets históricos en CI. Si la tasa de éxito o el MRR del retriever cae, se bloquea el PR.
*   **AI Gateway**: Proxy centralizado donde se configuran el ruteo de modelos, cache semántica, rate limits globales por token y failovers automáticos.
*   **Unified Observability**: Instrumentación end-to-end con OpenTelemetry exportando spans jerárquicos de LLM a LangFuse/Datadog.
*   **Cost Attribution**: Cada token consumido se etiqueta con `team_id`, `project_id` y `agent_id` desde el gateway, facilitando dashboards de control financiero precisos.
*   **Shared Memory**: Almacenamiento semántico centralizado (pgvector) que permite a distintos agentes compartir memorias a largo plazo entre dominios sin acoplamiento de bases de datos.

### 38. **¿Cómo manejás la multi-tenancy en una plataforma de agentes?**

La arquitectura multi-tenant en una plataforma de agentes requiere aislamiento estricto en tres niveles:

1.  **Aislamiento de Datos (Data Isolation)**:
    *   **Vector Search & Memory**: Cada chunk y memoria a largo plazo almacenada en pgvector contiene una columna indexada `tenant_id`. Las búsquedas semánticas obligatoriamente aplican filtros de metadatos estrictos (`WHERE tenant_id = :tenant_id`) para prevenir fugas de información inter-empresa o inter-equipo.
    *   **Context Isolation**: Al cargar documentos dinámicos a la ventana de contexto, el SDK interno inyecta validación de permisos de usuario para corroborar que el usuario que ejecuta el agente tiene acceso al recurso original.

2.  **Aislamiento de Cómputo e Infraestructura (Compute & Key Isolation)**:
    *   **Key Management**: El AI Gateway almacena de forma segura las credenciales y las API keys de los proveedores. Las llamadas se autorizan mediante firmas JWT y scopes asignados a cada tenant, evitando que un equipo acceda a las cuotas o cuentas de otro.
    *   **Rate-Limiting & Quotas**: Aplicamos límites de tokens por minuto (TPM) y requests por minuto (RPM) a nivel de `tenant_id` en el Gateway para evitar el efecto *"noisy neighbor"*, donde un agente bucleado de un equipo consume la cuota global del proveedor.

3.  **Audit Logs & Compliance**:
    *   Cada span generado por el runtime registra el ID del tenant. En caso de fallas de seguridad o auditorías de cumplimiento (GDPR, SOC2), los logs del sistema pueden filtrarse de manera aislada por tenant.

### 39. **¿Qué métricas a nivel plataforma trackeás para medir adopción y eficiencia?**

A nivel macro de plataforma corporativa, monitoreo:
*   **Developer Onboarding Velocity (Time-to-first-agent)**: Tiempo promedio desde que un equipo descarga el SDK interno hasta que despliega un agente funcional.
*   **Tool/Prompt Reuse Rate**: Porcentaje de herramientas y prompts consumidos desde el registro central vs. creados de forma personalizada por cada equipo.
*   **Infra Cost Efficiency**: Reducción de costos de API mediante el gateway (caching y routing óptimo).
*   **MTTR (Mean Time to Recovery)**: Tiempo promedio para apagar o corregir un agente con comportamiento errático usando el kill switch centralizado.
*   **Governance violations**: Tasa de llamadas bloqueadas por el `ToolGater` debido a violaciones de RBAC, PII o presupuesto.

---

## Sección 8: Preguntas Trampa y Cómo Responderlas

### 40. **"¿Cuál es tu experiencia con [tool específica que no conocés]?"**

**Respuesta de arquitecto**: *"No la usé en producción, pero entiendo perfectamente el problema que resuelve. En mi experiencia, la decisión no es qué herramienta específica usar, sino qué patrón arquitectónico aplicar. Si hablamos de orquestación de agentes, el patrón subyacente es un bucle ReAct apoyado por un event bus y un programador de tareas; esto lo implementé desde primeros principios en Python puro, y luego utilicé frameworks como LangGraph o CrewAI. La herramienta específica es secundaria; lo crítico es entender los trade-offs de diseño y cómo esa pieza encaja en el flujo global sin introducir complejidad accidental."*

### 41. **"¿Cómo manejarías las alucinaciones de un LLM?"**

**Respuesta de arquitecto**: *"Las alucinaciones no se resuelven mágicamente con un system prompt persuasivo. Se mitigan en tres capas del sistema:
*   **Capa de Datos (Retriever)**: Asegurando que la información suministrada al contexto del LLM sea de alta calidad y libre de ruido. Si el retriever tiene un Hit Rate y MRR altos, la probabilidad de alucinación decrece linealmente.
*   **Capa de Instrucción (System Prompt)**: Configurando reglas estrictas de abstención (*'si la respuesta no se deduce del contexto adjunto, di que no lo sabes'*).
*   **Capa de Validación (Evals)**: Evaluando en producción con frameworks de validación automatizada como G-Eval o validadores de consistencia factual estructurados, alertando si el score de alucinación cae por debajo de la norma."*

### 42. **"¿Cuándo NO usarías IA?"**

**Respuesta de arquitecto**: *"Cuando el problema puede resolverse eficazmente con lógica determinista, una base de datos relacional estándar, un simple script `if-else` o un motor de reglas de negocio clásico. He visto empresas gastar semanas y cientos de dólares en tokens entrenando agentes LLM para clasificar documentos en tres categorías estáticas; eso se resuelve con expresiones regulares o un switch-case tradicional. También evito IA generativa cuando las latencias de inferencia violan el acuerdo de nivel de servicio (SLA) del producto, cuando el costo por token destruye el modelo financiero del negocio, o cuando el costo de error es del 100% y no es viable una supervisión humana constante."*

### 43. **"¿Cómo medís el ROI de las iniciativas de IA?"**

**Respuesta de arquitecto**: *"Con métricas comerciales de negocio, no técnicas. No justifico un sistema diciendo que el modelo tiene un F1 score alto. Lo mido en:
1.  **Horas-hombre liberadas**: El tiempo neto que el agente le ahorra al equipo operativo al automatizar tareas rutinarias (ej. procesar facturas).
2.  **Reducción del costo operativo marginal**: El costo promedio de resolver un ticket de soporte con el agente vs. soporte humano de primera línea.
3.  **Reducción de tasas de error**: Errores costosos evitados en la extracción de datos en comparación con procesos manuales previos.
4.  **Costo de operación del agente**: Los costos acumulados de APIs de LLMs, bases vectoriales e infraestructura cloud.

El ROI real es la diferencia entre el valor de las horas optimizadas y la reducción de errores vs. la infraestructura total y mantenimiento del agente."*

### 44. **"¿Qué harías si un agente en producción empieza a comportarse de forma errática?"**

**Respuesta de arquitecto**: *"El orden de operaciones es:
1.  **Contención**: Activo el `kill switch` global o específico del agente desde la capa de gobernanza para pausar ejecuciones de tools que tengan efectos secundarios.
2.  **Aislamiento y Trazabilidad**: Utilizo el `trace_id` en el sistema de observabilidad (LangFuse/OTel) para rastrear el span exacto de la falla.
3.  **Rollback**: Si el fallo ocurrió tras cambiar una firma de tool o actualizar un prompt, hago un rollback inmediato en el Prompt Registry o la base de código.
4.  **Análisis de Regresión**: Integro el input problemático que causó el comportamiento errático en nuestro dataset de pruebas automáticas en CI. Esto garantiza que no vuelva a ocurrir tras la corrección definitiva.
5.  **Post-Mortem**: Documento el root cause para mejorar las políticas de prevención de seguridad de la plataforma."*

### 45. **"¿Stream o no stream? ¿Cuándo usar SSE?"**

**Respuesta de arquitecto**: *"Stream siempre que el usuario final sea un humano. En aplicaciones conversacionales, el tiempo hasta el primer token (TTFT) es el factor clave de experiencia de usuario (UX). SSE (Server-Sent Events) es el estándar técnico ideal sobre HTTP porque es unidireccional y de baja sobrecarga de protocolo en comparación con WebSockets. Sin embargo, si el agente está consumiendo servicios en segundo plano o el resultado es consumido por otro sistema computacional, el stream es innecesario; espero el bloque JSON estructurado completo de manera síncrona para evitar la sobrecarga de parsing parcial."*

---

## Sección 9: Preguntas que VOS Deberías Hacerles

### 46. **"¿Cuál es el estado actual de la infraestructura de IA? ¿Tienen agentes en producción o están empezando?"**

*Por qué hacerla*: Demuestra que pensás en el punto de partida real, no en un escenario ideal. La respuesta te dice si vas a construir desde cero o heredar deuda técnica.

### 47. **"¿Cómo se toma la decisión de build vs buy hoy? ¿Hay un framework estándar o cada equipo elige el suyo?"**

*Por qué hacerla*: Revela la madurez arquitectónica de la organización y si hay espacio real para un arquitecto que defina estándares, o si el rol es más operativo.

### 48. **"¿Qué proceso de negocio fue el primero en automatizarse y qué aprendieron de esa experiencia?"**

*Por qué hacerla*: Te da contexto sobre qué funcionó y qué no, y demuestra que te importan las lecciones aprendidas, no solo el roadmap futuro.

### 49. **"¿Cómo se mide el éxito de una iniciativa de IA? ¿Hay métricas de negocio definidas o las tengo que establecer yo?"**

*Por qué hacerla*: Si no tienen métricas, el rol incluye definir el framework de evaluación — eso es trabajo de arquitecto, no de ingeniero. Y te dice si la empresa entiende que IA necesita métricas propias.

### 50. **"¿Cuál es la relación entre el equipo de IA y los equipos de producto/operaciones? ¿Hay un product owner de IA o trabajo directamente con los founders?"**

*Por qué hacerla*: El JD dice "work directly with founders and leadership". Esta pregunta valida si eso es real o aspiracional, y te da información sobre tu posición en la estructura organizacional.

### 51. **"¿Tienen un sistema de observabilidad y evals en producción o es algo que voy a construir?"**

*Por qué hacerla*: Si no tienen observabilidad, tu primer mes va a ser instrumentar todo antes de poder mejorar nada. Es información crítica para calibrar expectativas. Y demuestra que entendés que sin observabilidad no hay mejora continua.

### 52. **"¿Cuál es el presupuesto mensual actual en APIs de LLMs y cómo se gestiona?"**

*Por qué hacerla*: Pregunta que pocos candidatos hacen y que revela la madurez operativa. Si no saben cuánto gastan, no tienen budget gates — y eso es un riesgo que vos vas a tener que resolver.

### 53. **"¿Qué rol juega MCP o la interoperabilidad en su estrategia de agentes actual?"**

*Por qué hacerla*: Posiciona al candidato como alguien que piensa en estándares y escalabilidad a largo plazo, no solo en el feature del sprint. Si no conocen MCP, es una oportunidad para educar y demostrar valor inmediato.

---

### Mapeo de Componentes de Referencia

| Tema | Wiki | Código |
|------|------|--------|
| Inferencia HTTP/SSE | [01_llm_inference](./01_llm_inference.md) | [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py) |
| RAG + pgvector | [02_rag_postgres_pgvector](./02_rag_postgres_pgvector.md) | [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py) |
| Agent Runtime | [03_agent_runtime](./03_agent_runtime.md) | [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py) |
| Observabilidad/Evals | [04_observability_and_evals](./04_observability_and_evals.md) | [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py) |
| Gobernanza/Seguridad | [05_governance_and_security](./05_governance_and_security.md) | [05_governance_and_security.py](../00_primitives_scratch/05_governance_and_security.py) |
| Ecosistema Frameworks | [06_framework_ecosystem](./06_framework_ecosystem.md) | `01_python_frameworks/` (20+ demos) |

### Demos de Frameworks Implementados

| Framework | Archivo | Patrón |
|-----------|---------|--------|
| LangGraph | `langgraph_demo.py` | Grafo de estados con ciclos |
| PydanticAI | `pydantic_ai_demo.py` | Tipado estático + DI |
| CrewAI | `crewai_demo.py` | Multi-agente colaborativo |
| OpenAI Agents SDK | `openai_agents_demo.py` | Agents nativos OpenAI |
| DeepAgents | `deepagents_demo.py` | Bateries-included harness |
| MCP | `mcp_demo.py` | Protocolo de interoperabilidad |
| DuckDB + LangGraph | `duckdb_langgraph_demo.py` | OLAP embebido + grafos |
| DuckDB + CrewAI | `duckdb_crewai_demo.py` | OLAP embebido + multi-agente |
| LanceDB + PydanticAI | `lancedb_pydanticai_demo.py` | Vectorial serverless + tipado |
| Fine-tuning | `finetuning_demo.py` | Ajuste fino supervisado |
| SQLite + MCP | `sqlite_mcp_server_demo.py` | MCP server sobre SQLite |
| SQLite + OpenAI Agents | `sqlite_openai_agents_demo.py` | Estado local + agents |
| **LlamaIndex Advanced RAG** | `llamaindex_advanced_demo.py` | RAG avanzado: routing, reranking, evaluation |
| **OpenRouter Multi-Model** | `openrouter_multi_model_demo.py` | Routing dinámico, modelos free, cost tracking |
| **MCP Educational Platform** | `mcp_educational_platform_demo.py` | Plataforma educativa completa con MCP |
| **MCP Virtual Wallet** | `mcp_virtual_wallet_demo.py` | Fintech: fraude, insights, disputas vía MCP |
