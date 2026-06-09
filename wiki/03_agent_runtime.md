# Anatomía de un Agent Runtime (Entorno de Ejecución de Agentes)

Un agente no es simplemente una llamada a un LLM en un bucle `while`. Para poder operar en entornos empresariales complejos de producción, un agente necesita una infraestructura que le proporcione persistencia, desacoplamiento, temporización, seguridad y control del estado. 

En esta guía analizaremos el diseño arquitectónico de un **Agent Runtime** desde cero. Veremos el bucle de razonamiento ReAct, la propagación implícita de contextos, la gestión desacoplada por eventos y la estructuración de la memoria a corto y largo plazo.

Vínculo al código de referencia: [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py)

---

## 🏛️ Bloques Arquitectónicos de un Agente de Producción

Un sistema de agentes moderno se divide en capas bien diferenciadas:

*   **Agent Runtime**: El motor principal que orquesta el ciclo de vida, la carga del contexto y el paso de ejecución.
*   **Workflow**: La definición estructurada del comportamiento (grafos, máquinas de estado o flujos secuenciales).
*   **Event Bus**: El canal de comunicación asíncrono que notifica cambios de estado y telemetría a otros servicios.
*   **Scheduler (Planificador)**: El gestor de colas que encola tareas diferidas o de ejecución recurrente.
*   **Memory Engine**: El sistema que decide qué información retener, consolidar y recuperar según el contexto.
*   **Governance & Context Propagation**: La capa transversal que inyecta seguridad e identifica de forma única cada llamada anidada.

> [!NOTE]
> Para un análisis detallado sobre cómo seleccionar, estructurar y optimizar la topología de estos workflows (Lineal, DAG, Cíclico/ReAct y Multi-Agente), consulte el [Decision Record de Arquitectura de Pipelines](./08_pipeline_architecture_adr.md).


```
       ┌──────────────────────────────────────────────────┐
       │                  AGENT RUNTIME                   │
       │                                                  │
       │   ┌────────────────────┐   ┌─────────────────┐   │
       │   │     Memory Engine  │   │  Context Prop.  │   │
       │   └──────────┬─────────┘   └────────┬────────┘   │
       │              ▼                      ▼            │
       │   ┌──────────────────────────────────────────┐   │
       │   │        Bucle de Razonamiento ReAct       │   │
       │   └────────────────────┬─────────────────────┘   │
       │                        │                         │
       │    ┌───────────────────┼───────────────────┐     │
       │    ▼                   ▼                   ▼     │
       │┌───────┐          ┌─────────┐         ┌─────────┐│
       ││ Tools │          │Scheduler│         │Event Bus││
       │└───────┘          └─────────┘         └─────────┘│
       └──────────────────────────────────────────────────┘
```

---

## 🔄 El Bucle ReAct (Reason + Act)

El bucle de ejecución estándar de un agente autónomo sigue el patrón **ReAct (Reasoning and Acting)**. En lugar de ejecutar código secuencial estructurado por un desarrollador, el agente decide de manera dinámica qué herramientas invocar y cómo procesar su resultado basándose en el estado actual.

En [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py#L153-L186), el motor ejecuta un bucle simplificado que emula este ciclo de razonamiento:
1.  **Pensamiento (Thought)**: El LLM analiza la meta del usuario y decide si requiere información externa. Busca en su base de conocimiento u opta por llamar a una herramienta.
2.  **Acción (Action)**: El agente invoca formalmente una herramienta (*Tool Calling*) pasando argumentos estructurados.
3.  **Observación (Observation)**: La herramienta se ejecuta y devuelve un texto plano del entorno (por ejemplo, el resultado de una consulta SQL).
4.  **Decisión Final**: Si la observación contiene los datos necesarios para resolver la meta original, el bucle finaliza formulando la respuesta al usuario. Si no, el bucle repite el ciclo (Thought -> Action -> Observation) con la nueva información.

---

## 📡 Bus de Eventos (Event Bus) y Planificación (Scheduler)

En un entorno asíncrono o de múltiples agentes, los componentes no deben llamarse directamente de forma dura (*tight coupling*). Usar un diseño guiado por eventos (**Event-Driven Design**) permite desacoplar la lógica.

### 1. Event Bus
En [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py#L50-L66) definimos un bus pub-sub síncrono. Los componentes del sistema (como los motores de observabilidad o auditoría de seguridad) pueden suscribirse a eventos como `tool_call_started` o `agent_completed` de forma independiente, sin modificar el código interno del agente.

```python
class EventBus:
    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def publish(self, event_type: str, payload: dict, context: ExecutionContext):
        payload["timestamp"] = time.time()
        if event_type in self.listeners:
            for listener in self.listeners[event_type]:
                listener(payload, context)
```

### 2. Task Scheduler
La ejecución de un agente puede tomar minutos o requerir reintentos ante fallos de red. Para evitar bloquear los hilos principales del servidor web, las ejecuciones de los agentes se encolan en un planificador (`TaskScheduler`), que las procesa secuencialmente en segundo plano:

```python
class TaskScheduler:
    def __init__(self):
        self.queue = []

    def schedule(self, fn: Callable, *args, **kwargs):
        self.queue.append((fn, list(args), kwargs))

    def run_all(self):
        while self.queue:
            fn, args, kwargs = self.queue.pop(0)
            fn(*args, **kwargs)
```

---

## 🧠 Memory Engine: Corto y Largo Plazo

Un agente sin memoria no tiene continuidad conversacional ni capacidad de mejorar en base a experiencias pasadas. La memoria de un agente se divide en dos categorías operativas:

1.  **Memoria a Corto Plazo (Short-term)**: Almacena secuencialmente la lista de mensajes de la conversación activa (`role` y `content`). Es lo que se pasa al LLM dentro de la ventana de contexto en cada llamada.
2.  **Memoria a Largo Plazo (Long-term)**: Un almacén consolidado que persiste a través de múltiples sesiones conversacionales de un mismo usuario. 
    *   *Simulación Vectorial*: Cuando el agente resuelve una tarea, extrae una síntesis estructurada del aprendizaje (consolidación de memoria) y la almacena en un índice clave-valor o en una base de datos vectorial (`pgvector`).
    *   *Recuperación (Recall)*: Al iniciar una nueva tarea, el runtime busca de forma no destructiva si existen experiencias pasadas almacenadas asociadas a palabras clave o semántica de la consulta:

```python
class MemoryEngine:
    def __init__(self):
        self.short_term = []
        self.long_term = {}

    def consolidate(self, key: str, synthesis: str):
        self.long_term[key] = {
            "synthesis": synthesis,
            "consolidated_at": time.time()
        }

    def recall(self, query_keyword: str) -> Optional[str]:
        for key, value in self.long_term.items():
            if query_keyword.lower() in key.lower():
                return value["synthesis"]
        return None
```

---

## 🪵 Propagación del Contexto (Context Propagation)

Cuando depuras un sistema distribuido o un agente complejo que genera sub-agentes y llama a docenas de herramientas, necesitas saber exactamente qué desencadenó una llamada particular de base de datos o de API.

Inspirado en los estándares de **OpenTelemetry**, implementamos la clase `ExecutionContext` en [03_agent_runtime_scratch.py](../00_primitives_scratch/03_agent_runtime_scratch.py#L21-L46). 

Cada hilo o ejecución conserva un contexto implícito que encapsula:
*   `trace_id`: Un identificador universal único para toda la interacción del usuario.
*   `parent_span_id`: El identificador de la tarea padre inmediata que provocó la ejecución.
*   `tenant_id`: El identificador del cliente corporativo que realiza la acción (garantiza la multi-tenencia).

Al ejecutar una herramienta, el runtime clona el contexto creando un hijo (`spawn_child`) en el que asocia la llamada de la herramienta con el `trace_id` original de la solicitud raíz:

```python
class ExecutionContext:
    def spawn_child(self) -> "ExecutionContext":
        return ExecutionContext(
            trace_id=self.trace_id,
            parent_span_id=str(uuid.uuid4())[:8],
            tenant_id=self.tenant_id
        )
```

Al propagar este objeto a través de cada llamada a funciones y eventos publicados en el `EventBus`, la capa de observabilidad puede construir de forma determinista el árbol de ejecución jerárquico completo del sistema, aislando problemas de latencia o fallos de seguridad.
