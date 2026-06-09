# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "lancedb>=0.15.0",
#     "pydantic-ai>=1.106.0",
#     "pydantic>=2.13.4",
# ]
# ///
"""
lancedb_pydanticai_demo.py

Integración de LanceDB (base de datos vectorial serverless/embebida) con PydanticAI.
Demuestra un pipeline RAG completo: creación de tabla, inserción de documentos con
embeddings reales, búsqueda por similitud coseno, búsqueda full-text y búsqueda híbrida,
todo expuesto como herramientas de un agente PydanticAI con validación estructural.

LanceDB es una BD vectorial embebida (sin servidor) que usa formato Lance (columnar),
ideal para pipelines RAG locales sin infraestructura externa.

Ejecución: uv run 01_python_frameworks/lancedb_pydanticai_demo.py
"""

import os
import tempfile
import math
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel
import lancedb

EMBEDDING_DIM = 8

SAMPLE_DOCUMENTS = [
    {
        "id": "doc_001",
        "title": "Retrieval Augmented Generation (RAG)",
        "content": "RAG combina modelos generativos con recuperación de documentos externos para reducir alucinaciones y mejorar la precisión factual en respuestas de LLMs.",
        "tags": "rag retrieval augmentation llm",
    },
    {
        "id": "doc_002",
        "title": "Embeddings y Espacios Vectoriales",
        "content": "Los embeddings son representaciones numéricas densas de texto en espacios vectoriales de alta dimensión. Permiten medir similitud semántica entre documentos mediante distancia coseno.",
        "tags": "embeddings vectors cosine similarity",
    },
    {
        "id": "doc_003",
        "title": "Fine-tuning de Modelos de Lenguaje",
        "content": "El fine-tuning ajusta los pesos de un modelo pre-entrenado con datos específicos del dominio. Técnicas como LoRA y QLoRA permiten adaptación eficiente en recursos.",
        "tags": "finetuning lora qlora training",
    },
    {
        "id": "doc_004",
        "title": "Arquitectura de Agentes con Herramientas",
        "content": "Los agentes de IA utilizan herramientas externas (APIs, bases de datos, buscadores) para extender sus capacidades más allá de la generación de texto puro.",
        "tags": "agents tools function-calling orchestration",
    },
    {
        "id": "doc_005",
        "title": "Bases de Datos Vectoriales",
        "content": "Las bases de datos vectoriales como LanceDB, Pinecone y Qdrant indexan embeddings para búsqueda de similitud eficiente usando algoritmos ANN (HNSW, IVF).",
        "tags": "vector database lancedb ann hnsw index",
    },
    {
        "id": "doc_006",
        "title": "Prompt Engineering Avanzado",
        "content": "Técnicas como Chain-of-Thought, Few-Shot y ReAct mejoran el razonamiento de LLMs mediante instrucciones estructuradas y ejemplos en el prompt.",
        "tags": "prompt engineering chain-of-thought react",
    },
]


def generate_embedding(text: str) -> list[float]:
    """Genera un embedding determinístico basado en hash del texto.
    No es un embedding semántico real, pero es consistente y reproducible."""
    h = hash(text)
    vec = []
    for i in range(EMBEDDING_DIM):
        val = math.sin(h * (i + 1) * 0.1) + math.cos(h * (i + 2) * 0.05)
        vec.append(val)
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


class SearchResult(BaseModel):
    id: str = Field(description="ID del documento encontrado")
    title: str = Field(description="Título del documento")
    content: str = Field(description="Contenido del documento")
    distance: float = Field(description="Distancia coseno (menor = más similar)")


class SearchResponse(BaseModel):
    query: str = Field(description="Consulta original del usuario")
    search_type: str = Field(description="Tipo de búsqueda realizada (vector, fulltext, hybrid)")
    results: list[SearchResult] = Field(description="Lista de resultados encontrados")
    summary: str = Field(description="Resumen analítico de los hallazgos")


class LanceDBDependencies(BaseModel):
    db_path: str = Field(description="Ruta al directorio de la base de datos LanceDB")
    table_name: str = Field(default="ai_docs", description="Nombre de la tabla en LanceDB")


def create_lancedb_table(db_path: str, table_name: str) -> lancedb.table.Table:
    """Crea la tabla en LanceDB e inserta los documentos de ejemplo con embeddings."""
    db = lancedb.connect(db_path)

    rows = []
    for doc in SAMPLE_DOCUMENTS:
        embedding = generate_embedding(doc["content"])
        rows.append({
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "tags": doc["tags"],
            "vector": embedding,
        })

    table = db.create_table(table_name, data=rows, mode="overwrite")
    table.create_fts_index("content", replace=True)
    return table


def build_agent(db_path: str, table_name: str) -> Agent:
    """Construye el agente PydanticAI con herramientas de búsqueda en LanceDB."""

    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        agent = Agent(
            "google-gla:gemini-2.0-flash",
            output_type=SearchResponse,
            deps_type=LanceDBDependencies,
            system_prompt=(
                "Eres un asistente especializado en ingeniería de IA y búsqueda semántica. "
                "Usas una base de datos vectorial LanceDB para encontrar documentos relevantes. "
                "Siempre busca en la base de datos antes de responder. "
                "Responde en español con análisis técnico preciso."
            ),
        )
    else:
        print("\n[INFO] No se encontró GEMINI_API_KEY. Usando TestModel de PydanticAI.")
        print("[INFO] Las operaciones de LanceDB son REALES. Solo el LLM es simulado.\n")
        agent = Agent(
            TestModel(
                custom_output_args=SearchResponse(
                    query="(simulada por TestModel)",
                    search_type="vector",
                    results=[
                        SearchResult(
                            id="doc_001",
                            title="Retrieval Augmented Generation (RAG)",
                            content="RAG combina modelos generativos con recuperación de documentos externos.",
                            distance=0.12,
                        )
                    ],
                    summary="Respuesta simulada por TestModel. Las búsquedas en LanceDB son reales.",
                )
            ),
            output_type=SearchResponse,
            deps_type=LanceDBDependencies,
        )

    @agent.tool
    def vector_search(ctx: RunContext[LanceDBDependencies], query: str, top_k: int = 3) -> str:
        """Busca documentos por similitud vectorial (distancia coseno) en LanceDB.
        Usa esta herramienta cuando el usuario hace preguntas conceptuales o semánticas."""
        db = lancedb.connect(ctx.deps.db_path)
        table = db.open_table(ctx.deps.table_name)
        query_embedding = generate_embedding(query)
        results = table.search(query_embedding).limit(top_k).to_list()

        output_lines = [f"Búsqueda vectorial para: '{query}' (top {top_k})\n"]
        for i, r in enumerate(results, 1):
            output_lines.append(
                f"  {i}. [{r['id']}] {r['title']} (distancia: {r.get('_distance', 'N/A'):.4f})\n"
                f"     {r['content'][:120]}..."
            )
        return "\n".join(output_lines)

    @agent.tool
    def fulltext_search(ctx: RunContext[LanceDBDependencies], query: str, top_k: int = 3) -> str:
        """Busca documentos por coincidencia de texto completo (full-text search) en LanceDB.
        Usa esta herramienta cuando el usuario busca términos específicos o palabras clave."""
        db = lancedb.connect(ctx.deps.db_path)
        table = db.open_table(ctx.deps.table_name)
        results = table.search(query, query_type="fts").limit(top_k).to_list()

        output_lines = [f"Búsqueda full-text para: '{query}' (top {top_k})\n"]
        for i, r in enumerate(results, 1):
            output_lines.append(
                f"  {i}. [{r['id']}] {r['title']} (score: {r.get('_score', 'N/A')})\n"
                f"     {r['content'][:120]}..."
            )
        return "\n".join(output_lines)

    @agent.tool
    def hybrid_search(ctx: RunContext[LanceDBDependencies], query: str, top_k: int = 3) -> str:
        """Búsqueda híbrida que combina similitud vectorial y full-text search en LanceDB.
        Usa esta herramienta para obtener los resultados más completos y balanceados."""
        db = lancedb.connect(ctx.deps.db_path)
        table = db.open_table(ctx.deps.table_name)
        query_embedding = generate_embedding(query)
        results = (
            table.search(query_type="hybrid")
            .vector(query_embedding)
            .text(query)
            .limit(top_k)
            .to_list()
        )

        output_lines = [f"Búsqueda híbrida para: '{query}' (top {top_k})\n"]
        for i, r in enumerate(results, 1):
            dist = r.get("_distance", "N/A")
            score = r.get("_relevance_score", "N/A")
            output_lines.append(
                f"  {i}. [{r['id']}] {r['title']} (distancia: {dist}, relevancia: {score})\n"
                f"     {r['content'][:120]}..."
            )
        return "\n".join(output_lines)

    return agent


def demo_raw_lancedb(db_path: str, table_name: str):
    """Demuestra operaciones crudas de LanceDB sin el agente."""
    print("=" * 64)
    print("  FASE 1: Operaciones directas sobre LanceDB (sin agente)")
    print("=" * 64)

    db = lancedb.connect(db_path)
    table = db.open_table(table_name)

    print(f"\n[1] Tabla '{table_name}' cargada con {table.count_rows()} documentos.")
    print(f"    Ruta de la BD: {db_path}")

    print("\n[2] Búsqueda vectorial (similitud coseno):")
    query_text = "cómo funcionan los embeddings y vectores"
    query_vec = generate_embedding(query_text)
    results = table.search(query_vec).limit(3).to_list()
    print(f"    Query: '{query_text}'")
    for i, r in enumerate(results, 1):
        print(f"    -> {i}. [{r['id']}] {r['title']} | distancia: {r.get('_distance', 'N/A'):.4f}")

    print("\n[3] Búsqueda full-text:")
    fts_query = "agentes herramientas"
    results_fts = table.search(fts_query, query_type="fts").limit(3).to_list()
    print(f"    Query: '{fts_query}'")
    for i, r in enumerate(results_fts, 1):
        print(f"    -> {i}. [{r['id']}] {r['title']} | score: {r.get('_score', 'N/A')}")

    print("\n[4] Búsqueda híbrida (vector + full-text):")
    hybrid_query = "base de datos vectorial indexación"
    hybrid_vec = generate_embedding(hybrid_query)
    results_hybrid = (
        table.search(query_type="hybrid")
        .vector(hybrid_vec)
        .text(hybrid_query)
        .limit(3)
        .to_list()
    )
    print(f"    Query: '{hybrid_query}'")
    for i, r in enumerate(results_hybrid, 1):
        dist = r.get("_distance", "N/A")
        rel = r.get("_relevance_score", "N/A")
        print(f"    -> {i}. [{r['id']}] {r['title']} | distancia: {dist}, relevancia: {rel}")


def demo_agent(db_path: str, table_name: str):
    """Demuestra el agente PydanticAI usando herramientas de LanceDB."""
    print("\n" + "=" * 64)
    print("  FASE 2: Agente PydanticAI con herramientas LanceDB")
    print("=" * 64)

    agent = build_agent(db_path, table_name)
    deps = LanceDBDependencies(db_path=db_path, table_name=table_name)

    queries = [
        "¿Qué es RAG y cómo mejora la precisión de los LLMs?",
        "¿Cuáles son las técnicas de prompt engineering más efectivas?",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n--- Consulta {i}: '{query}' ---")
        print("Procesando con agente PydanticAI + LanceDB...\n")
        result = agent.run_sync(query, deps=deps)
        response: SearchResponse = result.output

        print(f"  Tipo de búsqueda: {response.search_type}")
        print(f"  Resultados encontrados: {len(response.results)}")
        for r in response.results:
            print(f"    - [{r.id}] {r.title} (distancia: {r.distance})")
        print(f"  Resumen: {response.summary}")


def run_demo():
    print("\n=== LanceDB + PydanticAI | Pipeline RAG con Búsqueda Vectorial ===\n")

    with tempfile.TemporaryDirectory(prefix="lancedb_demo_") as tmpdir:
        table_name = "ai_docs"

        print(f"[SETUP] Creando base de datos LanceDB en: {tmpdir}")
        create_lancedb_table(tmpdir, table_name)
        print(f"[SETUP] Tabla '{table_name}' creada con {len(SAMPLE_DOCUMENTS)} documentos + índice FTS.\n")

        demo_raw_lancedb(tmpdir, table_name)
        demo_agent(tmpdir, table_name)

        print("\n" + "=" * 64)
        print("  Demo completada. La BD temporal fue eliminada automáticamente.")
        print("=" * 64)


if __name__ == "__main__":
    run_demo()
