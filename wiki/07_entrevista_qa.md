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

Frameworks como LangGraph, Temporal, Mastra y Gollem convergen hacia este modelo porque permite combinar autonomía con predictibilidad.

La mayoría de los sistemas de producción que construyo actualmente siguen este enfoque.

### 4. **¿Cómo manejás el estado y la persistencia entre sesiones de un agente?**

Con un Memory Engine de dos capas. La memoria a corto plazo es la lista de mensajes de la conversación activa que se inyecta en la ventana de contexto. La memoria a largo plazo persiste cross-session: cuando el agente resuelve una tarea exitosamente, se ejecuta una **consolidación** que extrae una síntesis estructurada y la almacena en un índice (key-value o vectorial en pgvector). Al iniciar una nueva tarea, el runtime hace un **recall** no destructivo buscando experiencias pasadas por similitud semántica. Esto está implementado desde cero en [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py). Para checkpointing de estado intermedio en grafos complejos, LangGraph tiene soporte nativo de snapshots, pero si construís desde cero, serializás el estado del grafo en Postgres con un `agent_state JSONB` por `session_id`.

### 5. **¿Cómo controlás costos en un sistema de agentes autónomos?**

En producción utilizo los métricos de uso reales que devuelven los proveedores (OpenAI, Anthropic, Gemini, OpenRouter, etc.) como fuente de verdad para facturación y observabilidad. Mantengo además una estimación previa de tokens para predecir costos antes de ejecutar una llamada y aplicar budget gates preventivos.

El sistema tiene tres mecanismos en cascada. Primero, un **CostTracker** en tiempo real que consume los `usage` tokens de las respuestas del proveedor y calcula el costo incremental con precios por millón de tokens parametrizados por modelo. Segundo, un **Budget Gate** acumulativo a nivel de runtime: si el costo diario supera un umbral (ej: $1.00 USD), el `ToolGater` bloquea todas las ejecuciones subsiguientes automáticamente. Tercero, un **rate limiter** de ventana deslizable que limita llamadas por minuto para evitar bucles infinitos.

Esto no es opcional — un agente con un bug en su bucle ReAct puede generar facturas de miles de dólares en minutos. Implementación completa en [Gobernanza y Seguridad](./05_governance_and_security.md).

### 6. **¿LangGraph, PydanticAI o construir desde cero? ¿Cómo decidís?**

Depende del contexto del negocio. **Construyo desde cero** cuando el producto core de IA es el diferenciador competitivo y necesito control total sobre latencia, costos y seguridad del gating — depurar fallos toma minutos en vez de horas. **PydanticAI** cuando necesito tipado estático estricto, inyección de dependencias y código agnóstico al modelo sin la sobrecarga cognitiva de LangChain. **LangGraph** cuando estoy en un entorno corporativo que ya usa LangSmith para observabilidad y necesito integrar decenas de APIs rápido. La tabla de decisión completa está en [Ecosistema de Frameworks](./06_framework_ecosystem.md). La trampa es adoptar LangGraph por default sin evaluar la complexity tax que introduce.

### 7. **¿Cómo manejás la concurrencia y las ejecuciones asíncronas de agentes?**

Con un **Event Bus** desacoplado y un **Task Scheduler**. El bus pub-sub permite que componentes como observabilidad y auditoría se suscriban a eventos (`tool_call_started`, `agent_completed`) sin modificar el código del agente. El scheduler encola ejecuciones de larga duración para procesarlas en background sin bloquear el request HTTP. En producción real, esto se traduce en Redis + Celery o BullMQ para colas de tareas, con SSE (Server-Sent Events) para mantener al cliente informado del progreso. Un agente que tarda 3 minutos no puede ejecutarse dentro del lifecycle de un request HTTP — necesitás colas, estado persistente y un mecanismo de notificación asíncrono.

### 8. **¿Cómo coordinás múltiples agentes?**

Existen varios patrones:

**Supervisor Pattern**: Un agente coordinador distribuye tareas a agentes especializados. Es el más común y el que implemento por defecto.

**Planner / Executor**: Un agente planifica la estrategia, otro ejecuta las acciones. Útil cuando la planificación requiere razonamiento de alto nivel separado de la ejecución.

**Handoff**: Un agente transfiere el control a otro cuando detecta un dominio específico. Es el patrón que usa OpenAI Agents SDK nativamente.

**Event-Driven Agents**: Los agentes se comunican mediante eventos publicados en un bus compartido. Más desacoplado pero más complejo de depurar.

**Mi preferencia**: Comenzar con un único agente bien diseñado. Agregar coordinación multi-agente sólo cuando existe una necesidad clara de separación de responsabilidades. El error más común es sobre-ingenierizar con multi-agente cuando un solo agente con buenas tools resuelve el problema.

### 9. **¿Cómo diseñás la memoria de un agente?**

Diferencio cuatro tipos:

**Working Memory**: Contexto inmediato de la conversación — los mensajes actuales en la ventana de contexto.

**Episodic Memory**: Experiencias específicas pasadas — "la última vez que el usuario preguntó sobre X, la respuesta fue Y".

**Semantic Memory**: Conocimiento consolidado sobre usuarios y procesos — preferencias, patrones de comportamiento, reglas de negocio aprendidas.

**Procedural Memory**: Patrones de comportamiento y reglas aprendidas — cómo el agente resuelve ciertos tipos de problemas de forma recurrente.

**Implementación típica**: Postgres + pgvector para almacenamiento vectorial, extracción automática de memorias al final de cada conversación exitosa, ranking por relevancia semántica en el recall, y consolidación periódica que fusiona memorias episódicas en semánticas. Inspirado en enfoques como Mem0, Zep y Letta.

---

## Sección 2: Context Engineering

> En 2026, el problema principal no es el modelo sino el contexto. Context Engineering, Retrieval y Routing son más importantes que RAG clásico.

### 9. **¿Qué es Context Engineering?**

La calidad de un agente depende más del contexto que recibe que del modelo que utiliza. Context Engineering es el diseño sistemático de: qué información incluir, qué información excluir, cuándo recuperarla y cómo comprimirla.

**Problemas comunes**:
- **Lost in the Middle**: Los modelos suelen ignorar información ubicada en el centro del contexto.
- **Context Bloat**: Agregar más contexto no siempre mejora resultados — a menudo los degrada.
- **Retrieval Noise**: Muchos chunks irrelevantes en el contexto confunden al modelo.

**Técnicas que aplico**:
- **Context Ranking**: Ordenar la información por relevancia antes de inyectarla.
- **Retrieval Fusion**: Combinar resultados de múltiples retrievers (vectorial + full-text + BM25).
- **Query Expansion**: Reformular la query del usuario para mejorar el recall del retriever.
- **Context Compression**: Resumir o truncar contexto que excede la ventana útil.
- **Reranking**: Un segundo modelo (cross-encoder) reordena los resultados del retriever por relevancia real.

### 9.1 **¿Cómo aprovechás ventanas de contexto grandes?**

Los modelos modernos permiten millones de tokens. Eso no significa que debamos enviar todo.

**Estrategia**:
1. Recuperar contexto relevante del retriever.
2. Rerankear con un cross-encoder.
3. Comprimir lo que no es esencial.
4. Construir contexto final con la información más relevante primero.

**Regla práctica**: Más contexto no implica mejores respuestas. Mejor contexto sí. Un contexto de 8K tokens bien curado suele superar a uno de 128K lleno de ruido.

### 9.2 **¿Cómo elegís qué modelo usar? (Model Routing)**

No todas las tareas necesitan el mejor modelo. Uso routing dinámico basado en complejidad de la tarea:

**Tareas simples** (clasificación, extracción, formatting):
- GPT-4.1 Mini, Gemini Flash, Qwen — bajo costo, baja latencia.

**Tareas complejas** (razonamiento multi-paso, análisis profundo):
- Claude Opus, GPT-5, Gemini Pro — mayor costo pero mejor razonamiento.

**Routing Dinámico**: El runtime puede decidir automáticamente basándose en costo, latencia, complejidad de la tarea y disponibilidad del proveedor antes de seleccionar un modelo. Esto reduce costos un 60-80% sin sacrificar calidad en las tareas que realmente necesitan modelos grandes.

---

## Sección 3: RAG y Bases de Datos Vectoriales

### 10. **¿Por qué PostgreSQL + pgvector y no una base vectorial dedicada?**

Para la mayoría de los casos empresariales que he visto (decenas de miles o millones bajos de documentos), PostgreSQL + pgvector suele ser suficiente y ofrece una excelente relación entre simplicidad operativa y funcionalidad. Cuatro razones: (1) **Operación simplificada** — no configuro, aseguro ni pago por un clúster vectorial adicional. (2) **Consistencia ACID** — si un registro se actualiza o elimina, su vector también, sin retrasos de sincronización. (3) **Consultas híbridas** — un simple `JOIN` SQL o `WHERE` sobre metadatos relacionales (`tenant_id`, permisos) al mismo tiempo que la búsqueda por similitud coseno. (4) **Madurez** — décadas de optimización en backups, réplicas, HA y seguridad empresarial.

Cuando aparecen requerimientos avanzados de escalabilidad, búsquedas híbridas complejas, sparse vectors o distribución geográfica, considero motores especializados como Qdrant o Weaviate. Análisis completo en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 11. **¿Cómo funciona la similitud coseno y por qué se usa en RAG?**

La similitud coseno mide el ángulo entre dos vectores en el espacio multidimensional. Si apuntan en la misma dirección (ángulo 0°), el coseno es 1.0 (máxima similitud semántica). Si son perpendiculares (90°), es 0.0. La fórmula es el producto punto normalizado por las magnitudes: `cos(u,v) = (u·v) / (||u|| × ||v||)`. PostgreSQL pgvector usa la **distancia coseno** (1 - similitud) como métrica de error, donde valores cercanos a 0 indican alta similitud. Lo implementé desde cero en Python puro sin NumPy en [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py). La ventaja sobre la distancia euclidiana es que la coseno es invariante a la magnitud del vector — captura similitud semántica independientemente de la longitud del texto.

### 12. **¿Qué estrategia de chunking usás y por qué?**

Depende del dominio. **Sliding Window** (ventana de W palabras con overlap de O palabras) es simple, predecible y funciona bien para documentos técnicos estructurados. **Semantic Chunking** es superior para documentos narrativos o heterogéneos: divide en oraciones, calcula embeddings de cada una, y cuando la similitud coseno entre oraciones adyacentes cae debajo de un umbral (ej: 0.85), detecta un cambio de tema y cierra el bloque. La clave que pocos mencionan: el chunking no se optimiza por intuición, se optimiza midiendo **Hit Rate @ K** y **MRR @ K** contra un ground truth etiquetado. Si cambiás el tamaño de ventana y el MRR baja, volvés atrás. Implementación y métricas en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 13. **¿Qué es un índice HNSW y por qué es crítico en producción?**

HNSW (Hierarchical Navigable Small World) es un grafo multicapa de proximidad que permite búsquedas aproximadas de vecinos más cercanos (ANN) en tiempo logarítmico. En vez de comparar el query vector contra todos los vectores de la tabla (búsqueda exacta O(n)), HNSW navega capas del grafo saltando nodos hasta converger en los vecinos más cercanos. En Postgres se crea con `CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)`. Es crítico porque sin él, cada búsqueda semántica haría un scan completo de la tabla — con millones de chunks, la latencia sería inaceptable. Combinado con un índice GIN sobre metadatos JSONB, tenés búsquedas híbridas de alto rendimiento.

### 14. **¿Cuándo usarías Qdrant, LanceDB o DuckDB en lugar de pgvector?**

**Qdrant** (Rust): cuando tengo cientos de millones de vectores, necesito latencia sub-milisegundo, vectores dispersos (sparse), compresión de vectores o escalado en clústeres distribuidos nativos. **LanceDB** (Rust, serverless): para aplicaciones locales, notebooks Jupyter, herramientas embebidas o entornos cloud donde no quiero pagar un servidor inactivo — es como SQLite pero para vectores, con formato columnar Lance optimizado para datos multimodales. **DuckDB**: no es base vectorial pura, sino motor OLAP embebido — lo uso para procesar eval datasets de RAG, analizar logs masivos de observabilidad o hacer cómputos de recuperación sobre tablas temporales en memoria. Análisis comparativo completo de 7 motores en [RAG y PGVector](./02_rag_postgres_pgvector.md).

### 15. **¿Cómo evaluás la calidad de un sistema RAG?**

Con dos métricas fundamentales contra un ground truth etiquetado. **Hit Rate @ K**: porcentaje de consultas donde el documento correcto aparece en los top K resultados. **MRR @ K (Mean Reciprocal Rank)**: pondera la posición del acierto — si el doc esperado es el 1° suma 1.0, si es el 2° suma 0.5, si es el 3° suma 0.33. MRR es más informativa que Hit Rate porque no es lo mismo acertar primero que tercero. El pipeline de mejora continua es: ajustar chunking → medir Hit Rate y MRR → ajustar overlap → volver a medir → cambiar modelo de embeddings → volver a medir. RAG no es magia: si el retriever trae basura, el LLM genera basura. Implementación en [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py).

---

## Sección 3: Transformación de IA Cross-Org

### 16. **¿Cómo identificás qué procesos de una organización automatizar primero con IA?**

Con un framework de tres ejes: **volumen** (¿cuántas veces se ejecuta por día/semana?), **valor cognitivo** (¿es repetitivo y de bajo juicio humano?) y **costo de error** (¿qué pasa si el agente se equivoca?). Los procesos de alto volumen, bajo valor cognitivo y bajo costo de error son los primeros candidatos. Ejemplo típico: clasificación de tickets de soporte, extracción de datos de facturas, generación de resúmenes de reuniones. Los procesos de alto juicio o alto costo de error (decisiones legales, aprobación de créditos) requieren human-in-the-loop. La trampa es empezar por lo "cool" en vez de lo que genera ROI medible.

### 17. **¿Qué es el flywheel de la "self-improving company"?**

Es el ciclo de retroalimentación donde cada proceso automatizado libera capacidad humana y genera datos que alimentan la siguiente automatización. El agente que clasifica tickets genera datos etiquetados que mejoran el modelo de clasificación. El agente que resume reuniones genera contexto que el agente de project management consume. Cada automatización exitosa reduce el costo marginal de la siguiente. El rol del arquitecto es diseñar la **arquitectura de datos transversal** que permita este flujo: telemetría de agentes → eval datasets → fine-tuning → mejor agente → más telemetría. Como se detalla en [Introducción](./00_introduccion.md), el verdadero impacto de la IA no es construir demos, es crear sistemas organizacionales que aprenden.

### 18. **¿Cómo comunicás decisiones técnicas de IA a stakeholders no técnicos?**

Traduciendo a impacto de negocio, no a arquitectura. En vez de "necesitamos un índice HNSW para optimizar la búsqueda ANN", digo "hoy el equipo de ventas tarda 15 minutos en encontrar información de un cliente; con este cambio, va a tardar 10 segundos". En vez de "el F1 score del retriever es 0.72", digo "de cada 10 respuestas que da el asistente, 7 son correctas y 3 necesitan revisión humana — vamos a subirlo a 9 de 10 en el próximo sprint". **Parte del trabajo del arquitecto es traducir complejidad técnica a impacto de negocio.**

### 18.1 **¿Dónde ponés la lógica: prompt, tool o workflow?**

Toda lógica determinista vive en código o workflow. El prompt sólo contiene instrucciones de comportamiento: tono, formato, límites. Cuanta más lógica crítica termine dentro del prompt, más difícil será testearla, versionarla y gobernarla. Uso tools para acciones con side effects (escribir en DB, llamar APIs). Uso workflows para orquestación determinista de pasos. El prompt es la capa más frágil: un cambio de versión del modelo puede romper comportamientos implícitos.

### 19. **¿Cómo priorizás iniciativas de IA cuando todo el mundo quiere "su" agente?**

Con una matriz de impacto vs. complejidad y un roadmap visible para toda la organización. Cada iniciativa se puntúa en: (1) horas-hombre ahorradas por mes, (2) complejidad técnica (¿tenemos los datos? ¿el proceso está documentado?), (3) dependencia de otras iniciativas. Las de alto impacto y baja complejidad van primero. Las de alto impacto y alta complejidad se planifican para el trimestre siguiente. Las de bajo impacto se descartan explícitamente — decir "no" es parte del trabajo del arquitecto. El error más común es construir agentes para todos los departamentos en paralelo sin terminar ninguno. Mejor un agente en producción que diez en demo.

### 20. **¿Cómo manejás el cambio cultural cuando introducís IA en un equipo que tiene miedo de ser reemplazado?**

Posicionando la IA como amplificador, no como reemplazo. El framing correcto es: "el agente se encarga de las 4 horas de trabajo repetitivo para que vos puedas dedicar esas 4 horas al trabajo estratégico que solo vos podés hacer". En la práctica, involucro a los domain experts desde el día uno en el diseño del agente — ellos definen los criterios de éxito, etiquetan el ground truth y validan las salidas. Cuando el equipo siente que el agente es "suyo" y no algo que "les imponen", la adopción se acelera. También es crítico tener un período de shadow mode donde el agente sugiere pero no ejecuta, para generar confianza gradual.

### 20.1 **¿Cuándo incorporás Human-in-the-Loop?**

Cuando el **costo de error es alto** o la **confianza es baja**:
- Decisiones financieras irreversibles (transferencias, aprobación de crédito)
- Cambios en producción que afectan a usuarios
- Acciones legales o de compliance
- Diagnósticos médicos

Patrón típico:
```
Agent → Confidence Score → < threshold → Human Review Queue → Approve/Reject → Agent aprende
```

El threshold se calibra con datos reales: empezás conservador (alto threshold, mucho HITL) y lo bajás a medida que el agente demuestra fiabilidad. En fintech y salud, HITL no es opcional — es requisito regulatorio.

---

## Sección 4: Observabilidad, Evaluación y Gobernanza

### 21. **¿Cómo depurás un agente que dio una respuesta incorrecta en producción?**

Con un árbol jerárquico de spans compatible con **OpenTelemetry** — mi objetivo es que toda la observabilidad de agentes termine en OTel porque me permite exportar a LangFuse, LangSmith, Datadog, SigNoz o cualquier backend compatible sin lock-in. Cada ejecución de agente genera un `trace_id` único que se propaga a través de cada llamada anidada (tool calls, queries a bases vectoriales, llamadas al LLM). Cada span registra: nombre, tipo, inputs, outputs, duración y `parent_span_id`. Cuando algo falla, busco el trace en LangFuse/LangSmith y veo exactamente dónde se rompió: ¿el retriever trajo chunks irrelevantes? ¿el LLM alucinó a pesar del contexto correcto? ¿una tool devolvió datos erróneos? Sin esta trazabilidad, depurar un agente es adivinar. Implementación completa de spans jerárquicos con exportación a formato LangFuse en [Observabilidad y Evals](./04_observability_and_evals.md).

### 22. **¿Qué métricas de evaluación usás para medir la calidad de un agente?**

Tres niveles según el tipo de output. **Exact Match** para respuestas deterministas (clasificación, extracción de campos): 1.0 si coincide exactamente, 0.0 si no. **F1 Token Overlap** para respuestas generativas más largas (resúmenes, respuestas RAG): mide precision y recall a nivel de palabras, tolerando variaciones sintácticas. **G-Eval (LLM como juez)** para outputs creativos o conversacionales donde las métricas de string fallan: un LLM avanzado evalúa con criterios objetivos, razonamiento paso a paso y puntuación discreta en escala 1-5.

Además de estas métricas básicas, utilizo técnicas más avanzadas:

- **Pairwise Evaluation**: comparación directa entre dos respuestas para determinar cuál es mejor
- **Arena Evaluation**: competencia entre variantes para detectar preferencias humanas
- **Human Review Sampling**: muestreo humano periódico para evitar sesgos del evaluador automático

**Principio**: No confío únicamente en una métrica. Combino métricas automáticas y validación humana. La clave es tener eval datasets versionados en Git junto con el código y los prompts — un cambio de un adjetivo en el system prompt puede alterar por completo la calidad de los outputs.

### 23. **¿Qué es el versionado de prompts y por qué es crítico?**

Un cambio de un adjetivo en el system prompt o una modificación en la firma de una tool puede desencadenar fallos en cascada. Los prompts no deben tratarse como configuración en base de datos que se actualiza sin control — deben gobernarse bajo el ciclo de vida del software estándar. Una versión del sistema (ej: `v1.2.0`) debe garantizar un estado fijo de: la plantilla del prompt, la versión del modelo (`gemini-1.5-flash-001` vs `002`), los hiperparámetros (temperatura, top-p) y la firma de las tools asociadas. Cada span de observabilidad debe inyectar metadatos con `prompt_version` y `agent_tag` para correlacionar caídas de rendimiento con cambios específicos en Git. Detallado en [Observabilidad y Evals](./04_observability_and_evals.md).

### 24. **¿Cómo implementás gobernanza de seguridad en un sistema de agentes?**

Con el principio fundamental: **la seguridad de un agente es un problema de ingeniería de sistemas, no un truco de redacción de prompts**. Nunca confío en que el modelo respete instrucciones de seguridad — un atacante con prompt injection puede anularlas. Implemento un `ToolGater` (patrón Wrapper, inspirado en el Agent Governance Toolkit de Microsoft) que intercepta cada llamada a herramienta y valida cinco capas antes de ejecutar: (1) **Kill Switch** — interruptor global de emergencia, (2) **RBAC** — rol del agente vs. permisos requeridos por la tool, (3) **Budget Gate** — costo acumulado vs. límite diario, (4) **Rate Limiting** — ventana deslizable de llamadas por minuto, (5) **PII Masking** — regex para emails y teléfonos que se redactan antes de enviar al LLM. Implementación completa en [Gobernanza y Seguridad](./05_governance_and_security.md).

### 25. **¿Qué es un kill switch y cuándo lo usarías?**

Un kill switch es un interruptor global de emergencia que, al activarse, cancela la ejecución de **cualquier** herramienta del sistema de forma inmediata. Se usa cuando detectás comportamiento anómalo en producción: un agente que entra en bucle infinito, un patrón de llamadas sospechoso, o una vulnerabilidad de seguridad descubierta. La diferencia con simplemente "apagar el servidor" es que el kill switch es granular y reversible — lo activás desde un dashboard, aislás el problema, y lo desactivás cuando está resuelto, sin downtime del resto del sistema. Es el último recurso de la capa de gobernanza y debe existir desde el día uno en producción.

### 26. **¿Cómo monitoreás costos financieros en tiempo real?**

El CostTracker utiliza los **usage metrics reales** reportados por cada proveedor (OpenAI, Anthropic, Gemini, OpenRouter, etc.) como fuente de verdad para observabilidad y facturación. Las estimaciones previas de tokens se utilizan únicamente para predicción de costos y budget enforcement preventivo.

El sistema tiene tres mecanismos en cascada. Primero, un **CostTracker** en tiempo real que consume los `usage` tokens de las respuestas del proveedor y calcula el costo incremental con precios por millón de tokens parametrizados por modelo. Segundo, un **Budget Gate** acumulativo a nivel de runtime: si el costo diario supera un umbral (ej: $1.00 USD), el `ToolGater` bloquea todas las ejecuciones subsiguientes automáticamente. Tercero, un **rate limiter** de ventana deslizable que limita llamadas por minuto para evitar bucles infinitos.

Esto no es opcional — un agente con un bug en su bucle ReAct puede generar facturas de miles de dólares en minutos. Implementación completa en [Gobernanza y Seguridad](./05_governance_and_security.md).

---

## Sección 5: Estrategia y Build vs Buy

### 27. **¿Cuándo construís desde cero y cuándo adoptás un framework?**

Tres criterios claros. **Construyo desde cero** cuando el producto core de IA es el diferenciador del negocio y necesito control total sobre latencia, costos y seguridad — la depuración toma minutos, no horas, y no tengo dependency hell. **Adopto un framework ligero** (PydanticAI, Mastra) cuando necesito tipado estático estricto y velocidad de desarrollo sin la sobrecarga de LangChain. **Adopto LangGraph/LangChain** cuando estoy en un entorno corporativo que ya usa su ecosistema (LangSmith, LangServe) y necesito integrar decenas de APIs rápido. La decisión se evalúa bajo el prisma del mantenimiento a largo plazo, no de la velocidad inicial. Matriz completa en [Ecosistema de Frameworks](./06_framework_ecosystem.md).

### 28. **¿Cuál es la "complexity tax" de LangChain y cuándo vale la pena pagarla?**

LangChain introdujo abstracciones pesadas (LCEL, chains, agents) que dificultan la depuración — las excepciones suelen estar enterradas bajo docenas de clases abstractas. Los breaking changes entre versiones son frecuentes y requieren refactorizaciones constantes. La dependency chain es profunda. **Vale la pena** cuando: (1) ya estás invertido en LangSmith para observabilidad corporativa, (2) necesitás integrar muchas APIs rápido con sus conectores pre-construidos, (3) el equipo ya conoce la sintaxis. **No vale la pena** cuando: (1) tu producto es el agente en sí mismo y necesitás control total, (2) tu stack es TypeScript (Mastra es mejor opción), (3) tenés un equipo pequeño que se beneficia más de entender el código que de abstraerlo.

### 29. **¿Cómo evaluás un framework nuevo (Mastra, CrewAI, DeepAgents, etc.)?**

Con cinco preguntas: (1) **¿Resuelve un problema que no puedo resolver razonablemente sin él?** — si es solo un wrapper sobre APIs, no lo necesito. (2) **¿Cuál es el costo de salida?** — si adoptarlo requiere reescribir toda mi arquitectura, el lock-in es demasiado alto. (3) **¿Quién lo mantiene y qué tan activo es?** — frameworks de IA mueren rápido; verifico commits semanales, issues abiertos y comunidad. (4) **¿Puedo reemplazarlo por mis propias primitivas en un sprint?** — si construir lo que el framework hace me toma 2 días, no necesito el framework. (5) **¿Es compatible con MCP?** — la interoperabilidad es el futuro; si el framework no soporta MCP como estándar de tools, es una apuesta arriesgada.

### 30. **¿Qué es MCP y por qué es relevante como estándar de interoperabilidad?**

MCP (Model Context Protocol) es un estándar abierto que unifica cómo los modelos consumen datos y exponen tools al runtime. En vez de escribir integraciones personalizadas para cada SDK (leer archivos, consultar Postgres, interactuar con Slack), MCP introduce un esquema cliente-servidor estandarizado. Los servidores MCP contienen las tools; los clientes MCP (runtimes de agentes) las consumen. Esto desacopla la infraestructura de tools del runtime del agente y permite reutilizar tools en cualquier framework de la industria.

MCP tiene el potencial de convertirse en un estándar importante de interoperabilidad entre agentes y herramientas, aunque el ecosistema todavía está madurando y es pronto para afirmar que tendrá la adopción universal que tuvo REST. Si una organización está construyendo un ecosistema de agentes cross-org, MCP debería ser parte de la arquitectura desde el día uno para evitar integraciones point-to-point que no escalan.

### 31. **¿Fine-tuning o RAG? ¿Cuándo usar cada uno?**

El orden moderno de inversión suele ser:

```
Prompting → RAG → Structured Outputs → Tool Use → Fine-tuning → Distillation
```

Muchas empresas nunca llegan a fine-tuning porque los pasos anteriores resuelven el 90% de los casos con una fracción del costo.

**RAG** (Prompt Engineering + contexto vectorial) es óptimo para inyectar conocimientos dinámicos de bases de datos y responder de forma contextual — es rápido de iterar, no requiere GPUs y los datos se actualizan en tiempo real.

**Fine-tuning** es óptimo cuando necesitás enseñar al modelo un formato sintáctico extremadamente específico, terminología de nicho (médica, legal) o reducir costos/latencia usando un modelo más pequeño (7B parámetros) entrenado para una tarea específica en vez de GPT-4o.

**Model Distillation** (tema 2026): evaluás GPT-5/Claude Opus en tareas críticas, generás un dataset de alta calidad, destilás sobre Qwen o Llama, y corrés local o mucho más barato. Es la forma principal de reducir costos manteniendo calidad en producción.

En la práctica, el 80% de los casos se resuelven con RAG bien implementado + Structured Outputs. Fine-tuning es para cuando RAG no alcanza o cuando el costo por token de un modelo grande no justifica la tarea. Análisis en [Ecosistema de Frameworks](./06_framework_ecosystem.md).

---

## Sección 6: Preguntas Trampa y Cómo Responderlas

### 32. **"¿Cuál es tu experiencia con [tool específica que no conocés]?"**

**Respuesta de arquitecto**: "No la usé en producción, pero entiendo el problema que resuelve. En mi experiencia, la decisión no es qué tool usar sino qué patrón arquitectónico aplicar. Por ejemplo, si hablamos de orquestación de agentes, el patrón es ReAct con event bus y scheduler — eso lo implementé desde cero en Python puro y también con LangGraph y CrewAI. La tool específica es secundaria; lo que importa es entender los trade-offs de cada enfoque y poder evaluar si la tool resuelve el problema sin introducir complejidad accidental."

### 33. **"¿Cómo manejarías las alucinaciones de un LLM?"**

**Respuesta de arquitecto**: "Las alucinaciones se atacan en tres capas, no con un truco de prompting. Capa 1: **RAG bien implementado** — si el retriever trae contexto correcto y suficiente, la probabilidad de alucinación baja drásticamente. Medimos Hit Rate y MRR para asegurar esto. Capa 2: **System prompt con instrucciones de abstención** — indicarle al modelo que si no encuentra la respuesta en el contexto, diga 'no lo sé' en vez de inventar. Capa 3: **Evals en producción** — G-Eval como juez automático que puntúa veracidad, con alertas cuando el score baja del umbral. La alucinación cero no existe, pero la alucinación controlada y detectada sí."

### 34. **"¿Cuándo NO usarías IA?"**

**Respuesta de arquitecto**: "Cuando el problema se resuelve con un `if-else`, una query SQL o una regla de negocio determinista. He visto equipos gastar semanas en construir un agente con LLM para clasificar documentos que tienen 3 categorías fijas — eso es un `switch` statement, no un agente. También evito IA cuando el costo de error es inaceptable sin supervisión humana (decisiones legales vinculantes, diagnósticos médicos), cuando la latencia del LLM no es compatible con el SLA del producto, o cuando el volumen de datos no justifica el costo de tokens. La madurez arquitectónica se demuestra sabiendo cuándo **no** usar IA."

### 35. **"¿Cómo medís el ROI de las iniciativas de IA?"**

**Respuesta de arquitecto**: "Con métricas de negocio, no técnicas. Para cada iniciativa defino: (1) **Horas-hombre ahorradas** — si el agente procesa 200 facturas/día que antes tomaban 15 minutos cada una, son 50 horas/día liberadas. (2) **Reducción de error** — si el agente clasifica tickets con 95% de accuracy vs. 80% humano, cada error evitado tiene un costo cuantificable. (3) **Time-to-value** — cuánto tarda un cliente nuevo en obtener valor con el agente vs. sin él. (4) **Costo operativo del agente** — tokens, infraestructura, mantenimiento. El ROI es: (valor generado - costo del agente) / costo del agente. Si no puedo cuantificarlo antes de construir, no construyo."

### 36. **"¿Qué harías si un agente en producción empieza a comportarse de forma errática?"**

**Respuesta de arquitecto**: "Primero, activo el kill switch para detener ejecuciones inmediatamente — la contención es lo primero. Segundo, busco el trace_id de las ejecuciones erráticas en el motor de observabilidad y analizo el árbol de spans: ¿fue un cambio en el prompt? ¿una tool que devolvió datos inesperados? ¿un cambio en la versión del modelo? Tercero, una vez identificado el root cause, revierto el cambio (prompt, modelo o tool) y desactivo el kill switch. Cuarto, agrego un eval de regresión al pipeline de CI que cubra el escenario que falló para que no vuelva a pasar. Quintero, post-mortem documentado. La clave es que todo esto sea posible en minutos, no en horas — por eso la observabilidad y los kill switches existen desde el día uno."

### 37. **"¿Stream o no stream? ¿Cuándo usar SSE?"**

**Respuesta de arquitecto**: "Siempre stream para interfaces de usuario — el TTFT (Time To First Token) es la métrica de UX más importante en aplicaciones de IA. Esperar 10 segundos a que el LLM complete toda su respuesta antes de mostrar algo destruye la experiencia. SSE (Server-Sent Events) con chunked transfer encoding es el estándar. Ahora, si el output del agente es consumido por otro sistema (no un humano), no tiene sentido streamear — hago una llamada síncrona y espero la respuesta completa. La complejidad de parsear SSE crudo sin SDK es real (los fragmentos de red no están alineados con los límites del JSON), pero lo implementé desde cero y funciona. Detallado en [Inferencia de LLMs](./01_llm_inference.md)."

---

## Sección 7: Preguntas que VOS Deberías Hacerles

### 38. **"¿Cuál es el estado actual de la infraestructura de IA? ¿Tienen agentes en producción o están empezando?"**

*Por qué hacerla*: Demuestra que pensás en el punto de partida real, no en un escenario ideal. La respuesta te dice si vas a construir desde cero o heredar deuda técnica.

### 39. **"¿Cómo se toma la decisión de build vs buy hoy? ¿Hay un framework estándar o cada equipo elige el suyo?"**

*Por qué hacerla*: Revela la madurez arquitectónica de la organización y si hay espacio real para un arquitecto que defina estándares, o si el rol es más operativo.

### 40. **"¿Qué proceso de negocio fue el primero en automatizarse y qué aprendieron de esa experiencia?"**

*Por qué hacerla*: Te da contexto sobre qué funcionó y qué no, y demuestra que te importan las lecciones aprendidas, no solo el roadmap futuro.

### 41. **"¿Cómo se mide el éxito de una iniciativa de IA? ¿Hay métricas de negocio definidas o las tengo que establecer yo?"**

*Por qué hacerla*: Si no tienen métricas, el rol incluye definir el framework de evaluación — eso es trabajo de arquitecto, no de ingeniero. Y te dice si la empresa entiende que IA necesita métricas propias.

### 42. **"¿Cuál es la relación entre el equipo de IA y los equipos de producto/operaciones? ¿Hay un product owner de IA o trabajo directamente con los founders?"**

*Por qué hacerla*: El JD dice "work directly with founders and leadership". Esta pregunta valida si eso es real o aspiracional, y te da información sobre tu posición en la estructura organizacional.

### 43. **"¿Tienen un sistema de observabilidad y evals en producción o es algo que voy a construir?"**

*Por qué hacerla*: Si no tienen observabilidad, tu primer mes va a ser instrumentar todo antes de poder mejorar nada. Es información crítica para calibrar expectativas. Y demuestra que entendés que sin observabilidad no hay mejora continua.

### 44. **"¿Cuál es el presupuesto mensual actual en APIs de LLMs y cómo se gestiona?"**

*Por qué hacerla*: Pregunta que pocos candidatos hacen y que revela la madurez operativa. Si no saben cuánto gastan, no tienen budget gates — y eso es un riesgo que vos vas a tener que resolver.

### 45. **"¿Qué rol juega MCP o la interoperabilidad en su estrategia de agentes actual?"**

*Por qué hacerla*: Posiciona al candidato como alguien que piensa en estándares y escalabilidad a largo plazo, no solo en el feature del sprint. Si no conocen MCP, es una oportunidad para educar y demostrar valor inmediato.

---

## Sección 8: Temas Avanzados de Arquitectura

### 46. **¿Qué es Context Engineering?**

La calidad de un agente depende más del contexto que recibe que del modelo que utiliza. Context Engineering es el diseño sistemático de: qué información incluir, qué información excluir, cuándo recuperarla y cómo comprimirla.

**Problemas comunes**:
- **Lost in the Middle**: Los modelos suelen ignorar información ubicada en el centro del contexto.
- **Context Bloat**: Agregar más contexto no siempre mejora resultados — a menudo los degrada.
- **Retrieval Noise**: Muchos chunks irrelevantes en el contexto confunden al modelo.

**Técnicas que aplico**:
- **Context Ranking**: Ordenar la información por relevancia antes de inyectarla.
- **Retrieval Fusion**: Combinar resultados de múltiples retrievers (vectorial + full-text + BM25).
- **Query Expansion**: Reformular la query del usuario para mejorar el recall del retriever.
- **Context Compression**: Resumir o truncar contexto que excede la ventana útil.
- **Reranking**: Un segundo modelo (cross-encoder) reordena los resultados del retriever por relevancia real.

### 47. **¿Cómo aprovechás ventanas de contexto grandes?**

Los modelos modernos permiten millones de tokens. Eso no significa que debamos enviar todo.

**Estrategia**:
1. Recuperar contexto relevante del retriever.
2. Rerankear con un cross-encoder.
3. Comprimir lo que no es esencial.
4. Construir contexto final con la información más relevante primero.

**Regla práctica**: Más contexto no implica mejores respuestas. Mejor contexto sí. Un contexto de 8K tokens bien curado suele superar a uno de 128K lleno de ruido.

### 48. **¿Cómo elegís qué modelo usar? (Model Routing)**

No todas las tareas necesitan el mejor modelo. Uso routing dinámico basado en complejidad de la tarea:

**Tareas simples** (clasificación, extracción, formatting):
- GPT-4.1 Mini, Gemini Flash, Qwen — bajo costo, baja latencia.

**Tareas complejas** (razonamiento multi-paso, análisis profundo):
- Claude Opus, GPT-5, Gemini Pro — mayor costo pero mejor razonamiento.

**Routing Dinámico**: El runtime puede decidir automáticamente basándose en costo, latencia, complejidad de la tarea y disponibilidad del proveedor antes de seleccionar un modelo. Esto reduce costos un 60-80% sin sacrificar calidad en las tareas que realmente necesitan modelos grandes.

### 49. **¿Qué es un AI Gateway?**

```
Aplicación → AI Gateway → OpenAI / Anthropic / Gemini / OpenRouter / Modelos locales
```

**Responsabilidades**:
- **Routing**: Dirigir requests al proveedor/modelo óptimo.
- **Rate limiting**: Control de cuotas por tenant, equipo o aplicación.
- **Cost tracking**: Visibilidad centralizada de gastos por proveedor.
- **Caching**: Cache semántica para queries repetidas.
- **Observabilidad**: Un solo punto de instrumentación para todas las llamadas.
- **Governance**: Policy enforcement centralizada (PII masking, content filtering).
- **Failover**: Si un proveedor cae, redirigir a otro automáticamente.

**Beneficio**: Las aplicaciones no dependen directamente de un proveedor específico. Cambiar de OpenAI a Anthropic es una configuración, no un refactor.

### 50. **¿Cómo evitás respuestas ambiguas? (Structured Outputs)**

Uso contratos estructurados. Nunca le pido al modelo que devuelva texto libre cuando necesito una estructura conocida. Le pido un contrato explícito.

**Mecanismos**:
- **JSON Schema**: Definir el esquema exacto de la respuesta esperada.
- **Pydantic**: Validación de tipos en Python con `output_type=MyModel`.
- **Tool Calling**: El modelo "llama" una tool con parámetros tipados — es structured output nativo.
- **Structured Outputs**: APIs nativas de OpenAI/Anthropic que garantizan conformidad con el schema.

**Beneficios**: Menos parsing, menos errores, integración más simple, mayor confiabilidad. Si el modelo no puede producir una respuesta válida según el schema, falla explícitamente en vez de devolver basura que rompe el pipeline downstream.

---

## Sección 9: AI Platform Architecture — Cómo escalar de 1 agente a 1000 agentes

### 51. **¿Cómo diseñarías una plataforma interna para que 20 equipos creen 200 agentes sin caos?**

El problema no es construir un agente — es permitir que toda la organización construya agentes de forma segura, gobernable y observable. Una **AI Platform** provee:

**Runtime común**: Un agente base tipado, testeable y versionado que todos los equipos extienden. Incluye: ReAct loop, event bus, scheduler, memory engine, governance hooks.

**Tool Registry**: Catálogo centralizado de tools versionadas con schemas, permisos, rate limits y documentación. Los equipos no reescriben `read_db` o `call_api` — la consumen del registry. Cada tool tiene tests, examples y SLA.

**Prompt Registry**: Prompts versionados con metadata (modelo, temperatura, versión, owner, eval results). Cambiar un prompt no rompe agentes en producción porque la versión está pinned en el runtime.

**Evaluation Framework**: Pipeline CI/CD para agents. Cada PR corre evals automáticas (faithfulness, relevancy, latency, cost). No se mergea si baja el score. Eval datasets versionados en Git.

**AI Gateway**: Capa única entre apps y proveedores. Routing, rate limiting, cost tracking, caching, observabilidad, governance, failover. Las apps no conocen proveedores.

**Observabilidad unificada**: OpenTelemetry end-to-end. Un trace_id sigue la request desde el gateway → runtime → tool → LLM. Exporta a LangFuse, Datadog, SigNoz sin lock-in.

**Governance centralizada**: Kill switch global, RBAC por tool, budget gates por team/project, PII masking, audit logging. Políticas definidas una vez, aplicadas en todos lados.

**Shared Memory**: Memoria semántica cross-agent y cross-team. Un agente de ventas aprende del agente de soporte sin acoplamiento.

**Cost Attribution**: Cada llamada al LLM tiene `team_id`, `project_id`, `agent_id`. Dashboards de costo por equipo, por agente, por feature. Alertas cuando un equipo se desvía del presupuesto.

**Agent Catalog**: Descubrimiento de agentes existentes. "¿Ya hay un agente que clasifica tickets?" Sí, versión 2.3, owner: equipo soporte, SLA: 99.9%, usa model X. Reusá en vez de reconstruir.

**SDK interno**: `pip install ai-platform-sdk`. Los equipos hacen `from ai_platform import Agent, tool, eval` y construyen en horas, no semanas.

Esto es **plataforma**, no framework. El framework resuelve "cómo hago un agente". La plataforma resuelve "cómo hago que 200 agentes convivan en producción".

### 52. **¿Qué métricas de plataforma trackeás?**

- **Agent density**: agentes activos / desarrolladores
- **Time-to-first-agent**: horas desde idea hasta producción
- **Reuse rate**: % de tools/prompts reusados vs. recreados
- **Eval pass rate**: % de PRs que pasan evals en CI
- **Cost per agent/mes**: presupuestado vs. real
- **MTTR (Mean Time To Recovery)**: cuánto tarda en detectarse y corregirse un agente errático
- **Governance violations**: intentos de bypass de budget/kill switch/PII

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
