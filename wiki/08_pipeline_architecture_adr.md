# Decision Record: Arquitectura de Pipelines, Cadenas y Topologías de Agentes

En la ingeniería de IA en producción, un sistema rara vez se limita a una única llamada a un LLM. Para resolver problemas complejos, estructuramos flujos de trabajo (*workflows*) en forma de cadenas, grafos o redes multi-agente. Este documento registra las decisiones arquitectónicas relativas al diseño de estas topologías, la optimización de sus Atributos de Calidad (NFRs), el gobierno de contratos y la aplicación de patrones de razonamiento avanzados.

---

## 1. Topología de Pipelines: Comparativa y Decisiones de Diseño

La topología define la forma en que los datos y el control fluyen a través de las distintas etapas del sistema. Cada topología introduce trade-offs específicos en términos de latencia, costo, predictibilidad y facilidad de prueba.

```
Topología Lineal:
[ Entrada ] ──► [ Etapa 1 ] ──► [ Etapa 2 ] ──► [ Salida ]

Topología DAG:
                 ┌──► [ Ruta A ] ──┐
[ Entrada ] ──► Routing             ├──► [ Consolidación ] ──► [ Salida ]
                 └──► [ Ruta B ] ──┘

Topología Cíclica (ReAct):
              ┌────────────────┐
              ▼                │
[ Entrada ] ──► [ Thought ] ──► [ Action ] ──► [ Observation ] ──► [ Decision ] ──► [ Salida ]
```

### Resumen Comparativo de Topologías

| Topología | Autonomía | Latencia | Costo | Predictibilidad | Complejidad de Testing | Casos de Uso Recomendados |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Lineal (Secuencial)** | Nula | Baja | Bajo | Máxima | Muy Baja | Procesamiento por lotes, extracción simple, formateo. |
| **DAG (Flujos Condicionales)**| Baja | Media | Medio | Alta | Media | Clasificación con rutas de procesamiento especializadas, pipelines RAG. |
| **Cíclica (ReAct Loop)** | Media/Alta | Alta | Variable | Baja | Alta | Asistentes interactivos, análisis de datos de exploración, soporte técnico. |
| **Multi-Agente** | Alta | Muy Alta | Alto | Muy Baja | Muy Alta | Simulación de roles complejos, desarrollo colaborativo de software. |

### Análisis Detallado y Enlaces a Código

#### A. Topología Lineal
*   **Mecánica**: El output del paso $N$ sirve estrictamente como input para el paso $N+1$. No hay bifurcaciones.
*   **Código de referencia**: La llamada secuencial básica simulada en la primitiva [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py) ilustra esta simplicidad lineal.
*   **Trade-off**: Es la topología más barata y rápida de ejecutar, pero es incapaz de adaptarse si una etapa previa produce un resultado de baja calidad o que requiere redirección.

#### B. DAG (Directed Acyclic Graph)
*   **Mecánica**: Los nodos representan tareas y las aristas la dirección del flujo. No se permiten ciclos (bucles de retorno). El control fluye condicionalmente (routing).
*   **Código de referencia**: Implementado mediante orquestación estructurada en [duckdb_langgraph_demo.py](../01_python_frameworks/duckdb_langgraph_demo.py), donde un enrutador dirige la consulta hacia diferentes sub-nodos sin retornar sobre pasos anteriores.
*   **Trade-off**: Excelente para paralelizar pasos independientes (por ejemplo, buscar en múltiples APIs simultáneamente) usando `asyncio`, aunque no permite corregir errores de forma autónoma repitiendo una etapa.

#### C. Cíclica (ReAct Loop)
*   **Mecánica**: Permite que el sistema vuelva a estados anteriores basándose en observaciones del entorno ( Thought $\to$ Action $\to$ Observation).
*   **Código de referencia**: Implementado desde cero en la primitiva [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py) mediante un bucle de ejecución con herramientas y memoria, y de forma declarativa con [langgraph_demo.py](../01_python_frameworks/langgraph_demo.py).
*   **Trade-off**: Máxima flexibilidad operativa. El agente puede reintentar una consulta SQL si falló el primer sintaxis. Sin embargo, requiere un estricto control de la profundidad del ciclo para evitar bucles infinitos y costos descontrolados.

#### D. Multi-Agente
*   **Mecánica**: Múltiples bucles ReAct independientes cooperan compartiendo un canal de comunicación (Event Bus, Handoff o Supervisor).
*   **Código de referencia**: Implementado utilizando frameworks en [crewai_demo.py](../01_python_frameworks/crewai_demo.py) (colaboración jerárquica) y [openai_agents_demo.py](../01_python_frameworks/openai_agents_demo.py) (patrón Handoff/Transferencia de control).
*   **Trade-off**: Permite la especialización de prompts y herramientas (reduciendo el ruido en el contexto de cada modelo), a costa de una latencia agregada severa y la dificultad de rastrear el origen de las alucinaciones.

---

## 2. Optimización por NFR (Non-Functional Requirements)

El diseño de un pipeline de IA requiere priorizar los requerimientos no funcionales (latencia, costo, disponibilidad y observabilidad) para asegurar la viabilidad comercial y operativa.

```
                             ┌───────────────┐
                             │  AI GATEWAY   │
                             └───────┬───────┘
                                     │ (Model Routing & Circuit Breaker)
                                     ▼
                      ┌─────────────────────────────┐
                      │   Dynamic Router / Fallback │
                      └──────┬───────────────┬──────┘
                             │ (Complex)     │ (Simple)
                             ▼               ▼
                      ┌─────────────┐ ┌─────────────┐
                      │ Large Model │ │ Small Model │
                      └─────────────┘ └─────────────┘
```

### A. Latencia: Paralelismo y Streaming (SSE)
*   **Ejecución Concurrente**: En topologías DAG, los sub-nodos independientes deben ejecutarse de forma paralela. Si una etapa requiere la respuesta de dos recuperadores RAG, ambos deben lanzarse concurrentemente.
*   **Streaming de Tokens**: Para interfaces de usuario, la latencia percibida (TTFT - Time-to-First-Token) es crítica. El pipeline debe soportar el flujo de datos segmentado (Server-Sent Events).
*   **Código de referencia**: La primitiva [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py#L90-L119) contiene la implementación de streaming HTTP/SSE sin dependencias de frameworks externos.

### B. Costo: Model Routing y Caching Semántico
*   **Model Routing**: No todas las decisiones requieren el modelo más inteligente y costoso. El routing dinámico evalúa la complejidad de la tarea (ej: clasificar una intención toma microsegundos en un modelo 8B frente a uno de 400B).
*   **Código de referencia**: En [openrouter_multi_model_demo.py](../01_python_frameworks/openrouter_multi_model_demo.py) se detalla cómo enrutar a modelos alternativos y medir dinámicamente los costos para aplicar límites de presupuesto.
*   **Caching Semántico**: Guardar las respuestas previas y buscar por similitud semántica (pgvector) antes de llamar al LLM. Si la similitud supera un umbral alto (ej: 0.96), se devuelve la respuesta en caché, reduciendo el costo a $0$.

### C. Disponibilidad: Fallbacks y Circuit Breakers
*   **Fallback Models**: Si una API de un proveedor (ej: Anthropic) responde con un código de error de rate limit (429) o timeout (504), el runtime debe desviar el request a una alternativa preconfigurada (ej: Gemini Pro en Google Cloud) en menos de 500ms.
*   **Circuit Breaker**: Si un modelo o herramienta falla de manera reiterada en una ventana de tiempo (ej: 5 fallos consecutivos), el circuit breaker se abre, cancelando inmediatamente llamadas futuras para evitar consumir recursos o incurrir en retardos innecesarios, sirviendo un contenido degradado controlado.
*   **Código de referencia**: Implementado de manera transversal mediante la encapsulación en el `ToolGater` y políticas de presupuesto en [05_governance_and_security.py](../00_primitives_scratch/05_governance_and_security.py).

### D. Observabilidad: OpenTelemetry Spans por Etapa
*   **Rastreabilidad de Contexto**: Cada paso del pipeline debe inyectar metadata y propagar el contexto transaccional (`trace_id`, `parent_span_id`). Esto permite visualizar el pipeline como un árbol jerárquico de ejecución.
*   **Código de referencia**: Detallado en la primitiva [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py), la cual instrumenta ejecuciones y las exporta estructuradamente para su posterior ingesta en sistemas de monitoreo compatibles (como LangFuse).

---

## 3. Contratos entre Etapas (Stage Contracts)

Para garantizar la estabilidad del sistema a largo plazo, cada etapa del pipeline debe comunicarse a través de contratos rigurosamente definidos.

```
┌─────────────┐                       ┌─────────────────────┐                       ┌─────────────┐
│  Etapa N-1  │ ──( JSON String )──►  │  Schema Validation  │ ──( Typed Object )──► │   Etapa N   │
└─────────────┘                       │  (Pydantic/Parser)  │                       └─────────────┘
                                      └─────────────────────┘
```

### A. Schema Validation (Output Parser)
*   **El problema**: Los LLMs son probabilísticos y no garantizan la estructura del texto de salida de forma nativa a menos que se apliquen validadores.
*   **La solución**: Forzar salidas estructuradas en el API del LLM (Structured Outputs) y parsear a nivel de aplicación usando esquemas de datos tipados.
*   **Código de referencia**: La demo de [pydantic_ai_demo.py](../01_python_frameworks/pydantic_ai_demo.py) ilustra la inyección de tipos y validación automática de respuestas basada en Pydantic, impidiendo que datos mal formateados pasen a etapas subsecuentes.

### B. Versionado de Prompts y Registro de Configuración
*   **El problema**: Modificar un adjetivo en un System Prompt de la etapa 1 puede alterar inesperadamente el output semántico, rompiendo las suposiciones de la etapa 2.
*   **La solución**: Los prompts deben versionarse en Git de forma estricta, mapeando el identificador de versión (`prompt_hash` o semantic versioning) a los metadatos de telemetría de cada Span de ejecución en producción.

### C. Compatibilidad hacia Atrás (Backward Compatibility)
*   Cuando cambie la interfaz de una herramienta (Tool Definition), se debe garantizar que el esquema sea retrocompatible (ej. definiendo campos opcionales con valores por defecto). De lo contrario, los agentes que tengan en caché o en memoria llamadas pendientes fallarán al ejecutar.

---

## 4. Patrones Avanzados de Pipelines y Cadenas

A continuación se detallan los patrones de refinamiento y post-procesamiento aplicados en arquitecturas de nivel senior:

```
Patrón Reranker en RAG:
[ Consulta ] ──┐
               ├──► [ Vector Search (pgvector) ] ──► [ 20 Chunks ] ──► [ Reranker (Cross-Encoder) ] ──► [ Top 3 Chunks ] ──► [ LLM ]
[ Documentos ] ┘

Patrón Ensemble Voting:
               ┌──► Model A (Claude) ──► Output A ──┐
[ Consulta ] ──┼──► Model B (GPT-4o) ──► Output B ──┼──► [ Consolidación / Votación ] ──► [ Respuesta Unificada ]
               └──► Model C (Gemini) ──► Output C ──┘
```

### A. Chain-of-Thought (CoT) como Etapa Explícita
*   **Mecánica**: En lugar de pedirle al modelo que devuelva directamente un formato final estructurado (como un JSON), se le entrena o instruye para que genere una etapa previa de pensamiento. Esto reduce drásticamente las alucinaciones al permitir que el LLM compute una trayectoria de razonamiento intermedia.
*   **Implementación**: Forzar al modelo a escribir dentro de tags `<thinking>...</thinking>` y luego extraer el bloque JSON limpio fuera de él como post-procesamiento.

### B. Reranker como Post-Proceso
*   **Mecánica**: En sistemas RAG, la búsqueda vectorial clásica basada en similitud coseno de embeddings de oraciones tiene limitaciones capturando relevancia exacta. Un reranker (modelo cross-encoder optimizado) evalúa la relevancia real de cada fragmento frente a la consulta del usuario.
*   **Código de referencia**: Implementado con precisión en [llamaindex_advanced_demo.py](../01_python_frameworks/llamaindex_advanced_demo.py), donde se recuperan 10-20 documentos candidatos y se filtran/reordenan a un grupo selecto de alta relevancia antes de inyectarlos en el prompt del LLM.

### C. Ensemble (Consenso Multi-Modelo)
*   **Mecánica**: Ejecutar la misma consulta de manera concurrente en múltiples modelos heterogéneos (ej: GPT-4o, Claude 3.5 Sonnet y Gemini 1.5 Pro) y resolver el resultado por votación mayoritaria (para tareas de clasificación) o mediante un LLM consolidador (para generación abierta).
*   **Beneficio**: Aumenta la robustez general ante fallos específicos o sesgos de un proveedor en particular.

### D. Speculative Decoding & Speculative Execution
*   **Decodificación Especulativa**: A nivel de inferencia, un modelo pequeño y veloz (ej: Llama-3B) propone drafts de tokens que el modelo grande (ej: Llama-70B) valida en un solo paso hacia adelante.
*   **Ejecución Especulativa en Pipelines**: Ejecutar una rama especulativa en paralelo con un modelo rápido basándose en la suposición de la ruta más probable del usuario. Si la predicción es correcta, se ahorra tiempo de cómputo; si es incorrecta, se descarta y se ejecuta la ruta real por el modelo principal.
