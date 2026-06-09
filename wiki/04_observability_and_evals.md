# Observabilidad, Trazas Jerárquicas y Evaluaciones (Evals)

A diferencia del software tradicional determinista, donde los fallos se detectan mediante excepciones de código o logs simples, los sistemas de Inteligencia Artificial Generativa fallan de manera silenciosa: el código finaliza sin errores, pero la respuesta devuelta por el modelo es incorrecta, sesgada o costosa.

En esta guía analizaremos cómo estructurar una arquitectura de **Observabilidad** basada en trazas jerárquicas compatible con **OpenTelemetry** como estándar abierto, permitiendo exportar a LangFuse, LangSmith, Datadog, SigNoz o cualquier backend compatible sin vendor lock-in. Detallaremos cómo programar métricas de **Evaluación Cuantitativa** (Exact Match y F1 Overlap), cómo orquestar jueces automáticos (**G-Eval**) y discutiremos las mejores prácticas para el **Versionado** conjunto de prompts y código.

Vínculo al código de referencia: [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py)

---

## 🪵 Trazabilidad Jerárquica y Estructura de Spans

Un agente corporativo puede ejecutar un flujo complejo que invoque herramientas, consulte bases vectoriales y realice múltiples llamadas anidadas a APIs de LLMs. Para poder depurar latencias y errores de ejecución, es fundamental modelar la telemetría como un **Árbol Jerárquico de Spans** (estándar OpenTelemetry):

```
[Trace: MainPipeline] (172ms)
   ├── [Span: DocumentRetriever] (50ms)
   └── [Span: LLMGenerator] (120ms)
          └── [Span: API_Request_Payload] (112ms)
```

En [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py#L20-L98) implementamos un gestor de contexto dinámico `TraceSpan`. Al utilizar una pila compartida (`active_span_stack`), cada nuevo span enlazado dentro de un bloque `with` reconoce automáticamente si tiene un span superior activo y se asocia a él como un nodo hijo de forma natural:

```python
class TraceSpan:
    active_span_stack = []

    def __init__(self, name: str, span_type: str = "generic", inputs: dict = None):
        self.name = name
        self.span_type = span_type
        self.inputs = inputs or {}
        self.children = []
        self.parent = None

    def __enter__(self):
        self.start_time = time.time()
        if TraceSpan.active_span_stack:
            self.parent = TraceSpan.active_span_stack[-1]
            self.parent.children.append(self)
        TraceSpan.active_span_stack.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        if exc_type is not None:
            self.outputs = {"status": "error", "error_message": str(exc_val)}
        TraceSpan.active_span_stack.pop()
```

---

## 🚀 Exportación a Formato OpenTelemetry / LangFuse / LangSmith

Aunque internamente el árbol de ejecución se construya de forma anidada y recursiva, los motores de telemetría de producción como **LangFuse**, **LangSmith**, **Datadog** o **SigNoz** ingieren las trazas a través de APIs compatibles con **OpenTelemetry** (OTLP). Esto requiere aplanar la jerarquía y registrar cada span con un identificador único y un puntero a su `parent_id`, siguiendo la especificación estándar.

El objetivo es que toda la observabilidad de agentes termine en OpenTelemetry porque permite exportar a cualquier backend compatible sin lock-in: hoy LangFuse, mañana Datadog, pasado SigNoz — el código de instrumentación no cambia.

En [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py#L71-L96), la función `serialize_langfuse_format` recorre el árbol de forma recursiva aplicando un patrón de aplanamiento compatible con OTLP:

```python
def serialize_langfuse_format(self) -> str:
    flat_records = []
    
    def flatten(span: "TraceSpan", parent_id: Optional[str] = None):
        span_id = f"span_{id(span)}"
        flat_records.append({
            "id": span_id,
            "parent_id": parent_id,
            "name": span.name,
            "type": span.span_type,
            "startTime": format_time(span.start_time),
            "endTime": format_time(span.end_time),
            "input": span.inputs,
            "output": span.outputs,
            "metadata": {"duration_sec": span.duration}
        })
        for child in span.children:
            flatten(child, parent_id=span_id)

    flatten(self)
    return json.dumps({"trace": flat_records}, indent=2)
```

---

## 📈 Métricas de Evaluación Cuantitativa (Evals)

El ajuste fino de prompts y modelos requiere pruebas de regresión automatizadas basadas en conjuntos de datos (*eval datasets*). Para evaluar la calidad del output, implementamos tres niveles de puntuación de precisión:

### 1. Exact Match (EM)
Es la métrica más restrictiva. Normaliza los textos (eliminando espacios en blanco adicionales y convirtiendo todo a minúsculas) y devuelve un valor binario: $1.0$ si la respuesta predicha coincide exactamente con la referencia de verdad, y $0.0$ si hay alguna discrepancia.

$$\text{Exact Match} = \begin{cases} 1.0 & \text{si } \text{Normalizar}(P) = \text{Normalizar}(R) \\ 0.0 & \text{en otro caso} \end{cases}$$

### 2. F1 Token Overlap (Precisión a Nivel de Palabras)
Para respuestas generativas más largas (e.g., resúmenes de RAG), la métrica Exact Match es inútil (fallará ante el mínimo cambio de sintaxis). En su lugar, tokenizamos la predicción ($P$) y la referencia ($R$) en listas de palabras y calculamos Precision, Recall y su media armónica F1:

*   **Precision (Precisión)**: Coincidencia de tokens sobre la predicción generada.
*   **Recall (Exhaustividad)**: Coincidencia de tokens sobre la referencia esperada.

$$\text{Precision} = \frac{|P \cap R|}{|P|}, \quad \text{Recall} = \frac{|P \cap R|}{|R|}$$

$$\text{F1} = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

En [04_observability_and_evals.py](../00_primitives_scratch/04_observability_and_evals.py#L107-L128):
```python
def compute_f1_token_overlap(prediction: str, reference: str) -> float:
    pred_tokens = prediction.strip().lower().split()
    ref_tokens = reference.strip().lower().split()
    ...
    common_tokens = set(pred_tokens) & set(ref_tokens)
    num_same = sum(min(pred_tokens.count(t), ref_tokens.count(t)) for t in common_tokens)
    
    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return (2 * precision * recall) / (precision + recall)
```

### 3. G-Eval (LLM como Juez)
Cuando el output es altamente creativo o conversacional (e.g., tono de voz, empatía), las métricas basadas en similitud de caracteres fallan. El patrón **G-Eval** utiliza un LLM avanzado con un prompt altamente estructurado que actúa como juez:
1.  Define criterios objetivos y explícitos de evaluación (por ejemplo, relevancia, veracidad o síntesis).
2.  Inyecta el prompt original del usuario y la respuesta a evaluar.
3.  Solicita al modelo razonar la calificación paso a paso.
4.  Fuerza una puntuación discreta (e.g., en una escala del 1 al 5) en un formato fácilmente analizable (e.g., `Score: [1-5]`).

---

## 🏷️ El Reto del Versionado (Prompt & Agent Versioning)

Un cambio de un solo adjetivo en el prompt de un agente del sistema o una ligera modificación en la firma de entrada de una herramienta puede desencadenar fallos catastróficos en cascada o alterar por completo la estructura semántica de los outputs de un LLM.

En producción, **los prompts no deben tratarse como configuración en base de datos externa que se actualiza sin control**. Deben gobernarse bajo el ciclo de vida del desarrollo de software estándar:

1.  **Versionado Acoplado en Código**: Los prompts deben residir en el control de versiones (Git) junto con las firmas de código que consumen sus salidas. Una versión del sistema de agentes (e.g., `v1.2.0`) debe garantizar un estado fijo de:
    *   La plantilla del prompt del agente.
    *   La versión específica del modelo consumido (e.g., `gemini-1.5-flash-001` vs. `gemini-1.5-flash-002`).
    *   La configuración de hiperparámetros (temperatura, top-p).
    *   La firma sintáctica de las herramientas asociadas al agente.
2.  **Etiquetado en Trazas**: Cada span registrado en el motor de observabilidad debe inyectar metadatos indicando la versión exacta del prompt y del agente ejecutado (`prompt_version`, `agent_tag`). Esto permite correlacionar caídas de rendimiento o incrementos de costo financiero detectados en las evaluaciones con cambios de versión específicos en Git.
