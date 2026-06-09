# Inferencia de LLMs y Protocolos de Red

El bloque fundamental de cualquier sistema basado en Inteligencia Artificial Generativa es la **Inferencia del Modelo**. Si bien frameworks comerciales como LangChain u OpenAI SDK simplifican las llamadas, ocultan los detalles del protocolo HTTP, la latencia de red y el costo computacional. 

En esta guía analizaremos cómo interactuar con LLMs (GPT, Claude, Gemini, Qwen, etc.) a nivel de socket y red utilizando únicamente la librería estándar de Python (`urllib.request`), cómo procesar texto en *streaming*, cómo estimar tokens/costo financiero en tiempo real, y cómo extraer salidas JSON válidas.

Vínculo al código de referencia: [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py)

---

## 🔌 Inferencia Cruda vía HTTP (Sin SDKs)

Cuando usas un SDK como `openai` o `google-generativeai`, estás utilizando una envoltura (*wrapper*) sobre una solicitud REST POST estándar. Construir la solicitud a mano nos da un control absoluto sobre los encabezados, tiempos de espera (*timeouts*) y el cuerpo del mensaje.

Tomemos como ejemplo la API de **Gemini** (modelo `gemini-1.5-flash`). La estructura de red para hacer una solicitud de generación de texto sin dependencias externas se construye de la siguiente manera:

```python
import json
import urllib.request

def call_gemini_api_raw(prompt: str, api_key: str, model: str = "gemini-1.5-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req) as response:
        resp_data = json.loads(response.read().decode("utf-8"))
        return resp_data["candidates"][0]["content"]["parts"][0]["text"]
```

Este patrón HTTP básico es idéntico para otros proveedores (e.g., OpenAI o Anthropic), cambiando únicamente la URL del endpoint y la estructura exacta del JSON (por ejemplo, el uso de arreglos de mensajes `messages` bajo los roles de `system`, `user` y `assistant`).

---

## 🌊 Procesamiento de Streaming SSE (Server-Sent Events)

Esperar a que un LLM complete toda su respuesta antes de enviarla a la interfaz de usuario arruina la experiencia de uso debido a la latencia del primer token (TTFT - *Time To First Token*). Los modelos devuelven tokens de forma progresiva utilizando el estándar de la industria **SSE (Server-Sent Events)** con transferencias codificadas por bloques (*Chunked Transfer Encoding*).

En [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py#L86-L134), implementamos un procesador de streams a bajo nivel. A medida que el socket de red recibe bytes del servidor de Google, leemos el búfer en fragmentos de 1KB:

```python
buffer = ""
while True:
    chunk = response.read(1024)
    if not chunk:
        break
    buffer += chunk.decode("utf-8")
```

El principal reto de procesar streaming crudo sin un SDK es que los fragmentos de red no están alineados con los límites del JSON. Un bloque de red puede cortar una palabra o un objeto JSON a la mitad. Para solucionarlo sin meter costosas dependencias de análisis léxico, el script escanea el búfer buscando el patrón `"text":` y extrae el valor entre comillas decodificando las secuencias de escape de manera segura:

```python
while "text" in buffer:
    idx = buffer.find('"text":')
    start_quote = buffer.find('"', idx + 7)
    # Encontrar la comilla de cierre ignorando comillas escapadas (\" )
    end_quote = start_quote + 1
    while True:
        end_quote = buffer.find('"', end_quote)
        if buffer[end_quote - 1] != '\\':
            break
        end_quote += 1
    
    extracted_text = buffer[start_quote + 1:end_quote]
    # Decodificar secuencias de escape (\n, \t, etc.)
    clean_text = bytes(extracted_text, "utf-8").decode("unicode_escape")
    yield clean_text
    buffer = buffer[end_quote + 1:]
```

Este es un enfoque pragmático que consume el stream de manera no bloqueante.

---

## 🪙 Estimación de Costos y Tokens en Tiempo Real

En producción, la observabilidad financiera es crítica. Lanzar agentes autónomos sin control de costos puede derivar en facturas imprevistas de miles de dólares debido a bucles infinitos de ejecución.

Dado que codificadores como Tiktoken (OpenAI) o SentencePiece (Gemini) añaden dependencias de binarios compilados en C, implementamos un estimador lineal simple en la clase `CostTracker` en [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py#L27-L53). Basado en la regla empírica del inglés y código, **1 token equivale aproximadamente a 4 caracteres**:

$$\text{Tokens Estimados} = \max\left(1, \frac{\text{Longitud del Texto}}{4}\right)$$

La clase asocia los precios oficiales por cada millón de tokens (e.g., Gemini 1.5 Flash cobra $\$0.075$ USD por millón de tokens de entrada y $\$0.30$ USD por millón de salida) y calcula el coste incremental en cada llamada de manera síncrona:

```python
class CostTracker:
    ...
    def track_response(self, response_text: str):
        tokens = self.estimate_tokens(response_text)
        self.output_tokens += tokens
        self.total_cost += (tokens / 1_000_000.0) * self.pricing["output"]
```

---

## 🧱 Extracción y Parsing de JSON Estructurado

Los LLM son motores predictivos de texto probabilísticos. Aunque se les solicite una salida en formato JSON, con frecuencia envuelven el resultado en bloques de código markdown (\`\`\`json ... \`\`\`) o añaden texto conversacional antes y después del bloque JSON.

Para obtener un diccionario de Python confiable en la capa de integración, implementamos la función `extract_and_parse_json` en [01_llm_inference_scratch.py](../00_primitives_scratch/01_llm_inference_scratch.py#L162-L186). 

La lógica escanea el texto buscando la primera llave de apertura `{` y la última llave de cierre `}`. Este delimitador físico aísla cualquier texto conversacional innecesario:

```python
def extract_and_parse_json(text: str) -> dict:
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    
    if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
        raise ValueError("No valid JSON structure found in response.")
        
    json_candidate = text[start_idx:end_idx + 1]
    return json.loads(json_candidate)
```

Este simple analizador limpia las imperfecciones de los modelos y garantiza que el sistema reciba un tipo de dato estructurado válido sin depender de librerías externas de validación de esquemas (e.g., Pydantic) durante la fase de análisis inicial.
