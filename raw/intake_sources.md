# Fuentes de Entrada Brutas (Raw Intake Sources)

Este archivo actúa como la bandeja de entrada inmutable del Vault de conocimiento, siguiendo las directrices de "LLM Wiki" de Andrej Karpathy. Contiene la transcripción textual y los recursos originales del cliente/usuario.

---

## 📄 Requisitos Crudos del Usuario (User Request)

### AI Engineering contiene:
* LLMs (GPT, Claude, Gemini, Qwen, etc.)
* RAG
* Agentes
* Memoria
* Evaluaciones (evals)
* Observabilidad
* Prompt engineering
* Fine-tuning
* MCP
* Seguridad
* Infraestructura
* Despliegue y operación

### Agent Harness Frameworks:
* LangChain -> LangGraph -> LangSmith -> LangServe -> LangMem -> LangFuse
* Mastra (https://github.com/mastra-ai/mastra)
* PydanticAI (https://github.com/pydantic/pydantic-ai)
* OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
* CrewAI (https://github.com/crewaiinc/crewai)
* Gollem (https://github.com/fugue-labs/gollem)
* Flue (https://github.com/withastro/flue)
* pi (https://github.com/earendil-works/pi/)

### Tópicos Críticos ("Poca gente sabe hablar de"):
* calidad de recuperación
* chunking
* versionado
* observabilidad
* evaluación
* costo
* seguridad
* permisos / Memory Engine

### Bloques de Arquitectura del Agente:
* Agent Runtime
* Scheduler
* Event Bus
* Governance
* Context Propagation
* Agent
* Workflow
* Memory
* Tracing
* Tool Calling
* Skills
* RAG
* Observability

### CTO / Enterprise RAG Stack:
* Para la mayoría de los casos de RAG empresarial suelo empezar con PostgreSQL + PGVector porque simplifica muchísimo la operación. Solo pensaría en una base vectorial dedicada cuando el volumen, la latencia o las capacidades de búsqueda lo justifican.
* Perfil: Mi experiencia no está solamente en construir funcionalidades de IA, sino en transformar organizaciones usando IA. Durante los últimos años trabajé como arquitecto, CTO y líder técnico construyendo plataformas complejas y equipos de ingeniería. Lo que más me entusiasma hoy es aplicar agentes, automatización e inteligencia artificial para eliminar trabajo manual, acelerar decisiones y crear organizaciones que aprenden y mejoran continuamente.

### Fuentes Externas a Clonar:
* https://github.com/rohitg00/ai-engineering-from-scratch
* https://github.com/patchy631/ai-engineering-hub
* https://github.com/microsoft/agent-governance-toolkit
* https://github.com/betta-tech/ejemplo-harness-subagentes
* https://github.com/Gentleman-Programming/gentle-ai
* https://github.com/Gentleman-Programming/engram
* https://github.com/lancedb/lancedb
* https://github.com/duckdb/duckdb
* https://github.com/etcd-io/bbolt
* https://github.com/dgraph-io/badger
* https://github.com/DavidLiedle/DriftDB
