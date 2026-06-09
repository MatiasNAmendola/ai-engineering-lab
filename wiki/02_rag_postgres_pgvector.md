# RAG y PGVector: Recuperación Semántica de Información

La generación aumentada por recuperación (RAG - *Retrieval-Augmented Generation*) resuelve las dos grandes limitaciones de los modelos de lenguaje: la falta de información propietaria/privada y las alucinaciones temporales. 

En esta guía construiremos desde cero la matemática vectorial necesaria, analizaremos las estrategias de segmentación de texto (*chunking*), detallaremos cómo estructurar índices híbridos en PostgreSQL utilizando la extensión `pgvector`, y definiremos métricas estadísticas para evaluar la calidad de recuperación (Hit Rate y MRR) sin recurrir a frameworks preconstruidos.

Vínculo al código de referencia: [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py)

---

## 📐 Matemáticas Vectoriales en Python Puro

Un *embedding* es una representación numérica (un vector de números flotantes de alta dimensión) que captura el significado semántico de un fragmento de texto. Para determinar qué tan similares son dos fragmentos, debemos calcular la distancia o el ángulo entre sus vectores correspondientes.

En [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py#L13-L40), implementamos estas operaciones matemáticas sin importar librerías numéricas externas como NumPy.

### 1. Producto Punto (Dot Product)
El producto punto mide la proyección de un vector sobre otro. Se calcula como la suma del producto de sus componentes correspondientes:

$$\mathbf{u} \cdot \mathbf{v} = \sum_{i=1}^{n} u_i v_i$$

```python
def dot_product(v1: list[float], v2: list[float]) -> float:
    return sum(x * y for x, y in zip(v1, v2))
```

### 2. Magnitud (Norma Euclidiana)
Representa la "longitud" física del vector desde el origen en el espacio multidimensional:

$$\|\mathbf{v}\| = \sqrt{\sum_{i=1}^{n} v_i^2}$$

```python
def magnitude(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))
```

### 3. Similitud Coseno
Es el coseno del ángulo formado por dos vectores. Si el ángulo es $0^\circ$ (vectores colineales que apuntan en la misma dirección), el coseno es $1.0$. Si son perpendiculares ($90^\circ$), el coseno es $0.0$.

$$\text{Similitud Coseno}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$

```python
def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    mag1 = magnitude(v1)
    mag2 = magnitude(v2)
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot_product(v1, v2) / (mag1 * mag2)
```

### 4. Distancia Coseno
Es la métrica de error inversa utilizada por los motores de búsqueda (incluido PostgreSQL pgvector). Se define como:

$$\text{Distancia Coseno}(\mathbf{u}, \mathbf{v}) = 1.0 - \text{Similitud Coseno}(\mathbf{u}, \mathbf{v})$$

Un valor cercano a $0.0$ indica alta similitud semántica.

---

## ✂️ Estrategias de Segmentación de Texto (Chunking)

Los modelos de embeddings tienen límites en su ventana de contexto (por ejemplo, 8192 tokens). Si pasamos un libro completo para generar un único vector, los matices y detalles específicos se promediarán y perderán en la alta dimensionalidad del vector. Por ello, debemos dividir el texto en fragmentos (*chunks*).

### 1. Sliding Window (Ventana Deslizable)
Divide el texto de forma secuencial en fragmentos de tamaño fijo ($W$ palabras) con una zona común de solapamiento ($O$ palabras) en los bordes para mantener la continuidad contextual de las oraciones:

En [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py#L43-L65):
```python
def sliding_window_chunking(text: str, window_size: int = 100, overlap: int = 20) -> list[str]:
    words = text.split()
    ...
    start = 0
    while start < len(words):
        end = start + window_size
        chunks.append(" ".join(words[start:end]))
        start += (window_size - overlap)
```

### 2. Semantic Chunking (Fragmentación Semántica)
El problema de la ventana deslizable es que corta a mitad de ideas o párrafos lógicos. La fragmentación semántica analiza la estructura gramatical:
1. Divide el texto en oraciones individuales.
2. Calcula los embeddings de cada oración.
3. Evalúa la similitud coseno entre oraciones adyacentes.
4. Si la similitud entre la oración $N$ y la oración $N+1$ cae por debajo de un umbral predefinido (e.g., $0.85$), se asume un **cambio de tema** y se cierra el bloque actual, iniciando uno nuevo.

```python
def semantic_chunking(text: str, similarity_threshold: float = 0.85) -> list[str]:
    # Separación simple por oraciones
    sentences = [s.strip() + "." for s in text.split(". ") if s.strip()]
    ...
    for i in range(1, len(sentences)):
        sim = cosine_similarity(get_embedding(sentences[i-1]), get_embedding(sentences[i]))
        if sim >= similarity_threshold:
            current_chunk.append(sentences[i])
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
```

---

## 🐘 Esquemas y Query Patterns en PostgreSQL + PGVector

Como se analizó en la introducción, PostgreSQL es el entorno operativo óptimo para la mayoría de los casos de RAG empresariales. La extensión `pgvector` introduce el tipo de datos `vector` e índices espaciales optimizados.

En [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py#L123-L159), definimos el esquema DDL mínimo para un entorno empresarial de producción:

```sql
-- Habilitar extensión
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla con segregación por metadatos relacionales y JSONB
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536), -- Dimensión para text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);
```

### Índices Críticos para Producción
1.  **HNSW (Hierarchical Navigable Small World)**: Crea un grafo multicapa de proximidad sobre los vectores. Es muy rápido para búsquedas aproximadas a gran escala utilizando el operador de distancia coseno (`<=>`):
    ```sql
    CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);
    ```
2.  **Índice GIN (Generalized Inverted Index)**: Permite indexar llaves y valores dinámicos dentro del campo JSONB `metadata` para filtros rápidos de multi-tenencia (*multi-tenancy*):
    ```sql
    CREATE INDEX ON document_chunks USING gin (metadata);
    ```

### Query Híbrido Relacional-Vectorial
Para buscar información restringiendo el acceso únicamente a los datos de un cliente (*tenant*) específico:

```sql
SELECT content, 1 - (embedding <=> :query_embedding) AS similarity
FROM document_chunks
WHERE metadata @> '{"tenant_id": "client_alpha"}'::jsonb
ORDER BY embedding <=> :query_embedding
LIMIT 5;
```

---

## 📈 Evaluación de la Calidad de Recuperación (Retrieval Evals)

No puedes optimizar el chunking, la longitud del solapamiento o el modelo de embeddings si no mides la calidad del motor de búsqueda. RAG no es magia; si el recuperador trae datos basura, el LLM generará basura.

En [02_rag_postgres_pgvector.py](../00_primitives_scratch/02_rag_postgres_pgvector.py#L164-L203), implementamos las dos métricas fundamentales de recuperación evaluadas a un corte $K$ (e.g., analizando los 3 mejores resultados):

### 1. Hit Rate @ K (Tasa de Acierto)
Mide el porcentaje de consultas en las que el documento correcto (esperado por un humano en un conjunto de pruebas) aparece dentro de los $K$ resultados recuperados por el sistema.

$$\text{Hit Rate@K} = \frac{\sum_{i=1}^{M} \mathbb{I}(\text{Doc Esperado}_i \in \text{Top K}_i)}{M}$$

Donde $\mathbb{I}$ es la función indicadora (retorna $1$ si es verdadero, $0$ si es falso) y $M$ es el número total de consultas evaluadas.

### 2. MRR @ K (Mean Reciprocal Rank)
El Hit Rate ignora la posición del resultado correcto (da igual si está en primer lugar o en el tercero). **MRR** soluciona esto ponderando la posición inversa del acierto. Si el documento esperado es el primer resultado, suma $1.0$. Si es el segundo, suma $0.5$. Si es el tercero, suma $0.33$. Si no aparece, suma $0.0$.

$$\text{MRR@K} = \frac{1}{M} \sum_{i=1}^{M} \frac{1}{\text{Posición Acierto}_i}$$

```python
def evaluate_retrieval_quality(ground_truth: list[dict], retrieved_results: list[list[str]], k: int = 3):
    hits = 0
    reciprocal_ranks = []
    
    for gt, retrieved in zip(ground_truth, retrieved_results):
        expected = gt["expected_doc"]
        top_k = retrieved[:k]
        
        # Hit Rate
        if expected in top_k:
            hits += 1
            # Reciprocal Rank
            rank = top_k.index(expected) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
            
    return hits / len(ground_truth), sum(reciprocal_ranks) / len(ground_truth)
```

Mediante la optimización continua de estas métricas se puede calibrar con precisión el pipeline de ingesta vectorial de datos en entornos empresariales.

---

## 🗄️ Análisis Comparativo de Bases de Datos (RAG, Vectores y Estado de Agentes)

Para diseñar la infraestructura de almacenamiento de un sistema de agentes o RAG corporativo, es crucial seleccionar el motor adecuado. A continuación, analizamos las bondades y diferencias clave de diversas alternativas de almacenamiento y bases de datos locales y dedicadas:

### 1. PostgreSQL + pgvector (Enfoque Relacional Pragmático)
*   **Bondades**: Motor relacional con soporte transaccional ACID maduro. Permite realizar búsquedas híbridas combinando filtros por metadatos (e.g., `tenant_id`, fecha de creación) y distancia coseno en una única consulta SQL optimizada mediante índices HNSW y GIN.
*   **Diferencia principal**: Es un motor multipropósito. Prioriza la simplicidad operativa, consistencia y facilidad de mantenimiento. Es el punto de partida ideal para la gran mayoría de casos de uso (95%), evitando la complejidad de sincronizar bases de datos separadas.

### 2. Qdrant y Weaviate (Motores Vectoriales Dedicados)
*   **Bondades**:
    *   **[Qdrant](https://github.com/qdrant/qdrant)** (escrito en Rust): Alto rendimiento computacional, latencia sub-milisegundo, soporte para vectores dispersos (*sparse vectors*), compresión de vectores y escalado en clústeres distribuidos nativos.
    *   **[Weaviate](https://github.com/weaviate/weaviate)** (escrito en Go): Alta facilidad de uso, GraphQL nativo, hibridación BM25/Dense integrada de forma nativa, y arquitectura modular con vectorización automatizada mediante integraciones de ML directo.
*   **Diferencia principal**: Son bases vectoriales puras y distribuidas. Se deben introducir únicamente cuando el volumen de embeddings supera las decenas de millones de registros, se requiere sub-milisegundo en búsquedas intensivas a gran escala, o se necesitan características vectoriales avanzadas ausentes en pgvector.

### 3. LanceDB (Búsqueda Vectorial Serverless y en Columnas)
*   **Bondades**: Base de datos vectorial serverless e *in-process* escrita en Rust. Utiliza el formato de datos en columnas "Lance", optimizado para consultas analíticas veloces, lectura directa de datos de imagen y audio (*multimodal*), y accesos aleatorios rápidos. No requiere un servidor independiente activo; almacena los datos directamente en local o en servicios de almacenamiento en la nube (e.g., AWS S3).
*   **Diferencia principal**: Es serverless como SQLite, pero optimizada para vectores y datos masivos en columnas. Ideal para aplicaciones locales, herramientas embebidas, cuadernos Jupyter, o entornos en la nube de coste cero por servidor inactivo.
*   *Repositorio clonado localmente para referencia:* **[lancedb](../external/lancedb)**

### 4. DuckDB (Análisis de Datos y Operaciones Vectoriales en Proceso)
*   **Bondades**: Motor SQL analítico (OLAP) embebido e *in-process*. Diseñado para consultas relacionales masivas de agregación de forma ultra-rápida. Permite hacer búsquedas y similitudes vectoriales utilizando funciones matemáticas nativas, procesar archivos Parquet y CSV directamente desde el disco de forma eficiente.
*   **Diferencia principal**: Es un motor analítico (no relacional OLTP ni base vectorial pura). Óptimo para procesar los conjuntos de datos de evaluación de RAG (*eval datasets*), analizar logs masivos de observabilidad, o realizar cómputos de recuperación sobre tablas temporales en memoria sin levantar un motor dedicado.
*   *Repositorio clonado localmente para referencia:* **[duckdb](../external/duckdb)**

### 5. bbolt (Almacén Key-Value Embebido y Transaccional)
*   **Bondades**: Motor key-value de bajo nivel, embebido y transaccional (ACID) escrito en Go. Utiliza una estructura de árbol B+ y escribe datos en un único archivo de disco de manera determinista y segura ante fallos de corriente.
*   **Diferencia principal**: No soporta indexación vectorial nativa ni consultas SQL. Es óptimo para la gestión de **Estado de Agentes** (Agent State), persistencia de configuraciones, bitácoras y memorias episódicas clave-valor en microservicios Go que requieran consistencia absoluta y cero dependencias de red.
*   *Repositorio clonado localmente para referencia:* **[bbolt](../external/bbolt)**

### 6. Badger (Key-Value LSM Tree de Alta Velocidad para Escrituras)
*   **Bondades**: Almacén key-value embebido en Go optimizado para SSDs. Implementa un árbol LSM (Log-Structured Merge-tree) con separación de claves y valores (WiscKey). Esto proporciona un rendimiento de escritura órdenes de magnitud superior a motores B+ tradicionales cuando los valores de los registros son grandes.
*   **Diferencia principal**: Comparado con bbolt, Badger es mucho más rápido en escrituras concurrentes masivas a costa de requerir más memoria RAM y recolección de basura (*value log GC*). Es ideal para almacenar históricos de chat gigantescos, ventanas de contexto crudas, o embeddings como pares clave-valor crudos antes de su indexación.
*   *Repositorio clonado localmente para referencia:* **[badger](../external/badger)**

### 7. DriftDB (Sincronización en Tiempo Real y Colaboración)
*   **Bondades**: Base de datos de paso de mensajes y sincronización de estado local-first y en tiempo real a través de WebSockets.
*   **Diferencia principal**: No es una base de datos de persistencia a largo plazo o de búsqueda matemática. Está diseñada específicamente para la **sincronización instantánea de estado** en aplicaciones colaborativas. Es ideal para construir interfaces de usuario en tiempo real que muestren el pensamiento o trazas del agente al usuario final a medida que ocurren (*human-in-the-loop*).
*   *Repositorio clonado localmente para referencia:* **[driftdb](../external/driftdb)**
