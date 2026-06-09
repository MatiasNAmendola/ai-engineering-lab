# Ingesta Bruta: Chain/Pipeline Architecture Decision Record (ADR)

Este archivo sirve como bandeja de entrada inmutable para el nuevo análisis técnico que se integrará en la Wiki.

## Contenido a Desarrollar

### 1. Topología de Pipelines de Agentes
- **Lineal**: Cadenas secuenciales (A -> B -> C). Adecuado para tareas predecibles y fijas.
- **DAG (Grafo Acíclico Dirigido)**: Flujos con ramificación condicional pero sin ciclos. Excelente para orquestaciones semi-complejas donde se dividen responsabilidades.
- **Cíclico (ReAct)**: Bucles autónomos de razonamiento (Thought -> Action -> Observation). Máxima flexibilidad pero costo, latencia y predictibilidad variables.
- **Multi-agente**: Colaboración entre agentes independientes (Supervisor, Planner/Executor, Handoff). Complejidad adicional a cambio de especialización.

### 2. Optimización por NFR (Non-Functional Requirements)
- **Latencia**: Técnicas de paralelismo en ramas DAG, Streaming (SSE) para reducir el Time-To-First-Token (TTFT) en la UI.
- **Costo**: Model Routing dinámico (small -> large), cache semántica, model distillation.
- **Disponibilidad**: Fallbacks automáticos entre proveedores, circuit breakers para evitar loops de fallos y reintentos infinitos.
- **Observabilidad**: Spans estructurados por etapa, propagación de trace_id y parent_span_id a través de todo el grafo.

### 3. Contratos entre Etapas (Stage Contracts)
- **Schema Validation**: Output parsing estricto con Pydantic, Structured Outputs nativos de APIs de LLM.
- **Versionado de Prompts**: Pinning de plantillas, inyección de metadatos de versión en logs de observabilidad.
- **Compatibilidad hacia atrás**: Evitar que cambios en firmas de tools o prompts rompan stages posteriores del pipeline.

### 4. Patrones de Refinamiento y Post-proceso
- **Chain-of-Thought como etapa explícita**: Separación clara de razonamiento y formateo de salida (bloques de pensamiento explícitos).
- **Reranker como post-proceso**: Uso de cross-encoders para ordenar chunks en RAG y reducir ruido del contexto.
- **Ensemble (Votación)**: Consenso de múltiples modelos para aumentar confiabilidad en tareas críticas.
- **Speculative decoding / Speculative Execution**: Ejecuciones rápidas o drafts de modelos pequeños evaluados por modelos más grandes.
