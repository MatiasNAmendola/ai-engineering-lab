# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai>=1.0.0",
# ]
# ///
"""
finetuning_demo.py

Demostración educativa de conceptos de Fine-tuning con OpenAI:
1. Preparación de datos de entrenamiento en formato JSONL.
2. Validación de datos: formato, conteo de tokens y calidad.
3. Creación de jobs de fine-tuning vía API (patrones de uso).
4. Evaluación comparativa: modelo base vs modelo fine-tuned.
5. Análisis de costo/latencia: fine-tuning vs prompt engineering.

Este demo funciona en MODO OFFLINE sin necesidad de API key.
Genera datos de ejemplo, los valida, y muestra los patrones de la API.

Ejecución: uv run 01_python_frameworks/finetuning_demo.py
"""

import json
import os
import tempfile
from pathlib import Path


# ==========================================
# 1. GENERACIÓN DE DATOS DE ENTRENAMIENTO
# ==========================================

SYSTEM_PROMPT = (
    "Eres un experto en bases de datos especializado en PostgreSQL, pgvector, "
    "índices vectoriales y optimización de consultas SQL para aplicaciones de IA."
)

TRAINING_EXAMPLES = [
    {
        "user": "¿Qué tipo de índice debo usar para búsqueda de vecinos más cercanos en pgvector?",
        "assistant": (
            "Para búsqueda ANN (Approximate Nearest Neighbor) en pgvector, "
            "el índice HNSW (Hierarchical Navigable Small World) es óptimo. "
            "Ofrece mejor recall que IVFFlat con un trade-off en uso de memoria. "
            "Creación: CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        ),
    },
    {
        "user": "¿Cómo optimizo una consulta SQL que genera embeddings al vuelo?",
        "assistant": (
            "Evita generar embeddings en cada consulta. En su lugar: "
            "1) Pre-computa los embeddings y almacénalos en una columna VECTOR. "
            "2) Usa un índice HNSW sobre esa columna. "
            "3) Para la consulta, usa el operador <=> (distancia coseno): "
            "SELECT * FROM docs ORDER BY embedding <=> $1 LIMIT 10;"
        ),
    },
    {
        "user": "¿Cuál es la diferencia entre IVFFlat y HNSW en pgvector?",
        "assistant": (
            "IVFFlat divide el espacio vectorial en 'nlist' clusters y busca solo en los "
            "más cercanos. Es más rápido de construir pero tiene menor recall. "
            "HNSW construye un grafo de navegación multi-capa con mejor recall (~0.95+) "
            "pero consume más memoria y tarda más en construirse. "
            "Recomendación: HNSW para <10M de vectores, IVFFlat para datasets masivos "
            "donde la memoria es limitada."
        ),
    },
    {
        "user": "¿Cómo configuro pgvector para 1 millón de documentos?",
        "assistant": (
            "Para 1M de documentos con embeddings de 1536 dimensiones: "
            "1) ALTER SYSTEM SET maintenance_work_mem = '2GB'; "
            "2) CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 200); "
            "3) SET hnsw.ef_search = 100; para consultas. "
            "Tamaño estimado del índice: ~10 GB en disco."
        ),
    },
    {
        "user": "¿Qué función de distancia debo usar para embeddings de OpenAI?",
        "assistant": (
            "Para embeddings de OpenAI (text-embedding-3-small/large), usa distancia "
            "coseno con el operador <=>. Los embeddings de OpenAI ya están normalizados, "
            "por lo que coseno y producto interno (<#>) dan resultados equivalentes. "
            "Coseno es la opción más segura y estándar: "
            "SELECT *, 1 - (embedding <=> $1) AS similitud "
            "FROM documentos ORDER BY embedding <=> $1 LIMIT 5;"
        ),
    },
    {
        "user": "¿Cómo hago batch insert de vectores eficientemente en PostgreSQL?",
        "assistant": (
            "Para inserción masiva de vectores: "
            "1) Desactiva índices temporalmente: DROP INDEX si existe, recrear después. "
            "2) Usa COPY en lugar de INSERT para cargas >10K filas. "
            "3) Aumenta maintenance_work_mem antes de crear el índice. "
            "4) Crea el índice HNSW DESPUÉS de cargar todos los datos. "
            "Ejemplo: COPY documentos (texto, embedding) FROM '/data/vectors.csv' CSV;"
        ),
    },
    {
        "user": "¿Qué dimensiones tienen los modelos de embedding más usados?",
        "assistant": (
            "Dimensiones de modelos populares: "
            "- OpenAI text-embedding-3-small: 1536 dimensiones. "
            "- OpenAI text-embedding-3-large: 3072 dimensiones (reducible con Matryoshka). "
            "- Cohere embed-v3: 1024 dimensiones. "
            "- BGE-large: 1024 dimensiones. "
            "- E5-large-v2: 1024 dimensiones. "
            "Tip: text-embedding-3-small ofrece el mejor ratio calidad/precio para la mayoría de casos."
        ),
    },
    {
        "user": "¿Cómo implemento RAG con PostgreSQL y pgvector?",
        "assistant": (
            "Pipeline RAG con PostgreSQL: "
            "1) Indexación: Divide documentos en chunks, genera embeddings, almacena en tabla con columna VECTOR. "
            "2) Retrieval: Busca los top-K chunks más similares a la query del usuario usando <=>. "
            "3) Generation: Envía los chunks recuperados como contexto al LLM junto con la pregunta. "
            "SQL de retrieval: SELECT chunk_text FROM doc_chunks "
            "ORDER BY embedding <=> encode(query_embedding) LIMIT 5;"
        ),
    },
]


def generate_training_data() -> list[dict]:
    """Convierte los ejemplos raw al formato JSONL requerido por OpenAI."""
    training_data = []
    for example in TRAINING_EXAMPLES:
        training_data.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": example["user"]},
                {"role": "assistant", "content": example["assistant"]},
            ]
        })
    return training_data


# ==========================================
# 2. VALIDACIÓN DE DATOS
# ==========================================

def estimate_tokens(text: str) -> int:
    """Estimación aproximada de tokens (1 token ≈ 4 caracteres en inglés/español)."""
    return len(text) // 4


def validate_training_data(data: list[dict]) -> dict:
    """Valida el formato y calidad de los datos de entrenamiento."""
    errors = []
    warnings = []
    total_tokens = 0
    max_tokens = 0
    min_tokens = float("inf")

    for i, example in enumerate(data):
        if "messages" not in example:
            errors.append(f"Ejemplo {i}: falta la clave 'messages'")
            continue

        messages = example["messages"]
        if len(messages) < 2:
            errors.append(f"Ejemplo {i}: se necesitan al menos 2 mensajes (user + assistant)")
            continue

        roles = [m.get("role") for m in messages]
        if "assistant" not in roles:
            errors.append(f"Ejemplo {i}: falta el mensaje con rol 'assistant'")
        if "user" not in roles:
            errors.append(f"Ejemplo {i}: falta el mensaje con rol 'user'")

        example_text = " ".join(m.get("content", "") for m in messages)
        tokens = estimate_tokens(example_text)
        total_tokens += tokens
        max_tokens = max(max_tokens, tokens)
        min_tokens = min(min_tokens, tokens)

        if tokens > 4096:
            warnings.append(f"Ejemplo {i}: {tokens} tokens (puede ser costoso)")
        if tokens < 10:
            warnings.append(f"Ejemplo {i}: solo {tokens} tokens (ejemplo muy corto)")

    avg_tokens = total_tokens / len(data) if data else 0

    return {
        "total_examples": len(data),
        "errors": errors,
        "warnings": warnings,
        "is_valid": len(errors) == 0,
        "token_stats": {
            "total": total_tokens,
            "average": round(avg_tokens),
            "max": max_tokens,
            "min": min_tokens if min_tokens != float("inf") else 0,
        },
    }


# ==========================================
# 3. PATRONES DE LA API DE FINE-TUNING
# ==========================================

def show_api_patterns():
    """Muestra los patrones de uso de la API de fine-tuning de OpenAI."""
    print("  Código para crear un job de fine-tuning:\n")
    print("  ```python")
    print("  from openai import OpenAI")
    print("  client = OpenAI()")
    print()
    print("  # 1. Subir archivo de entrenamiento")
    print('  with open("training_data.jsonl", "rb") as f:')
    print('      response = client.files.create(file=f, purpose="fine-tune")')
    print()
    print("  # 2. Crear el job de fine-tuning")
    print("  job = client.fine_tuning.jobs.create(")
    print('      training_file=response.id,')
    print('      model="gpt-4o-mini-2024-07-18",')
    print("      hyperparameters={")
    print('          "n_epochs": 3,')
    print('          "batch_size": 4,')
    print('          "learning_rate_multiplier": 2.0,')
    print("      }")
    print("  )")
    print()
    print("  # 3. Monitorear el progreso")
    print("  job_status = client.fine_tuning.jobs.retrieve(job.id)")
    print("  print(job_status.status)  # 'running', 'succeeded', 'failed'")
    print()
    print("  # 4. Usar el modelo fine-tuned")
    print('  ft_model = job_status.fine_tuned_model  # "ft:gpt-4o-mini-2024-07-18:org::abc123"')
    print("  response = client.chat.completions.create(")
    print("      model=ft_model,")
    print('      messages=[{"role": "user", "content": "¿Qué índice uso para ANN?"}]')
    print("  )")
    print("  ```\n")


# ==========================================
# 4. COMPARACIÓN: MODELO BASE vs FINE-TUNED
# ==========================================

MOCK_COMPARISONS = [
    {
        "question": "¿Qué índice uso para búsqueda vectorial con 500K documentos?",
        "base_model": (
            "Para búsqueda vectorial podrías usar varios tipos de índices. "
            "Los más comunes son los índices basados en árboles o hash. "
            "Depende de tu base de datos específica."
        ),
        "fine_tuned_model": (
            "Para 500K documentos en pgvector, usa un índice HNSW: "
            "CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64). "
            "Tamaño estimado: ~5 GB. Set hnsw.ef_search = 80 para buen recall."
        ),
    },
    {
        "question": "¿Cómo reduzco la latencia de mis queries de similitud?",
        "base_model": (
            "Puedes optimizar las consultas agregando índices, usando caché, "
            "o reduciendo la cantidad de datos a buscar."
        ),
        "fine_tuned_model": (
            "Para reducir latencia en queries de similitud con pgvector: "
            "1) Usa índice HNSW con ef_search=50 (balance velocidad/recall). "
            "2) Reduce dimensionalidad con text-embedding-3-small y Matryoshka (512 dims). "
            "3) Filtra con WHERE antes del ORDER BY para reducir el espacio de búsqueda. "
            "4) Usa connection pooling con PgBouncer."
        ),
    },
]


def show_comparison():
    """Muestra la comparación entre respuestas del modelo base y fine-tuned."""
    for i, comp in enumerate(MOCK_COMPARISONS, 1):
        print(f"  --- Ejemplo {i} ---")
        print(f"  Pregunta: {comp['question']}\n")
        print(f"  [Modelo Base] {comp['base_model']}\n")
        print(f"  [Fine-Tuned]  {comp['fine_tuned_model']}\n")


# ==========================================
# 5. ANÁLISIS DE COSTO Y LATENCIA
# ==========================================

COST_ANALYSIS = {
    "prompt_engineering": {
        "setup_cost": "$0 (solo tiempo de desarrollo)",
        "cost_per_query": "~$0.002 (gpt-4o-mini con system prompt largo)",
        "latency": "~800ms (incluye system prompt de ~500 tokens)",
        "maintenance": "Actualizar el prompt manualmente",
        "best_for": "Prototipos, pocos ejemplos de contexto",
    },
    "fine_tuning": {
        "setup_cost": "~$5-50 (entrenamiento, depende de epochs y datos)",
        "cost_per_query": "~$0.001 (sin system prompt largo necesario)",
        "latency": "~500ms (sin overhead de system prompt extenso)",
        "maintenance": "Re-entrenar con nuevos datos",
        "best_for": "Dominios específicos, >100 ejemplos, producción",
    },
    "rag": {
        "setup_cost": "$0-10 (infraestructura de vector DB)",
        "cost_per_query": "~$0.003 (retrieval + generación con contexto)",
        "latency": "~1200ms (retrieval + generación)",
        "maintenance": "Mantener índice vectorial actualizado",
        "best_for": "Conocimiento cambiante, documentos extensos",
    },
}


def show_cost_analysis():
    """Muestra el análisis comparativo de costo y latencia."""
    for approach, metrics in COST_ANALYSIS.items():
        label = approach.replace("_", " ").title()
        print(f"  --- {label} ---")
        for metric, value in metrics.items():
            print(f"    {metric.replace('_', ' ').capitalize()}: {value}")
        print()


# ==========================================
# ENTRY POINT
# ==========================================

def run_demo():
    print("==========================================================")
    print("  Fine-tuning con OpenAI - Demo Educativa")
    print("==========================================================\n")

    # Paso 1: Generación de datos
    print("--- Paso 1: Generación de Datos de Entrenamiento ---")
    print("Convirtiendo ejemplos raw al formato JSONL de OpenAI...\n")

    training_data = generate_training_data()
    print(f"  Se generaron {len(training_data)} ejemplos de entrenamiento.\n")

    print("  Ejemplo de entrada JSONL (primer registro):")
    print(f"  {json.dumps(training_data[0], ensure_ascii=False, indent=4)}\n")

    # Paso 2: Escritura a archivo temporal y validación
    print("--- Paso 2: Validación de Datos ---")
    validation = validate_training_data(training_data)

    print(f"  Total de ejemplos:  {validation['total_examples']}")
    print(f"  Formato válido:     {'Sí' if validation['is_valid'] else 'No'}")
    print(f"  Errores:            {len(validation['errors'])}")
    print(f"  Advertencias:       {len(validation['warnings'])}")
    print(f"  Tokens totales:     {validation['token_stats']['total']}")
    print(f"  Tokens promedio:    {validation['token_stats']['average']}")
    print(f"  Tokens máximos:     {validation['token_stats']['max']}")
    print(f"  Tokens mínimos:     {validation['token_stats']['min']}\n")

    if validation["errors"]:
        print("  Errores encontrados:")
        for err in validation["errors"]:
            print(f"    - {err}")
        print()

    if validation["warnings"]:
        print("  Advertencias:")
        for warn in validation["warnings"]:
            print(f"    - {warn}")
        print()

    # Escritura del JSONL a archivo temporal
    tmp_path = Path(tempfile.gettempdir()) / "finetuning_training_data.jsonl"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for entry in training_data:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Archivo JSONL escrito en: {tmp_path}\n")

    # Paso 3: Patrones de la API
    print("--- Paso 3: Patrones de la API de Fine-tuning ---")
    print("  (La ejecución real requiere OPENAI_API_KEY)\n")

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        print("  [INFO] OPENAI_API_KEY detectada. Mostrando patrones de la API.")
        print("  [INFO] Para ejecutar el fine-tuning real, descomenta el código abajo.\n")
    else:
        print("  [NOTE] Sin OPENAI_API_KEY. Mostrando patrones de uso de la API.\n")

    show_api_patterns()

    # Paso 4: Comparación base vs fine-tuned
    print("--- Paso 4: Comparación Modelo Base vs Fine-Tuned (Simulado) ---\n")
    show_comparison()

    # Paso 5: Análisis de costo
    print("--- Paso 5: Análisis de Costo y Latencia ---\n")
    show_cost_analysis()

    print("--- Conclusión ---")
    print("  Fine-tuning es ideal cuando:")
    print("    - Tenés >100 ejemplos de alta calidad de un dominio específico.")
    print("    - Necesitás respuestas consistentes y especializadas.")
    print("    - Querés reducir latencia eliminando system prompts extensos.")
    print()
    print("  Prompt Engineering o RAG son mejores cuando:")
    print("    - El conocimiento cambia frecuentemente.")
    print("    - Tenés pocos ejemplos o el dominio es amplio.")
    print("    - Necesitás citar fuentes o documentos específicos.\n")

    print("==========================================================")
    print("  Fin de la demostración")
    print("==========================================================")


if __name__ == "__main__":
    run_demo()
