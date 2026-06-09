# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai-agents>=0.17.4",
# ]
# ///
"""
sqlite_openai_agents_demo.py

Demostración de integración entre SQLite real y el SDK de OpenAI Agents
para construir un agente de administración de bases de datos.

Patrón SQLite-como-PostgreSQL:
  Este archivo usa SQLite (stdlib, sin servidor) como stand-in de PostgreSQL+pgvector.
  Cada herramienta ejecuta queries SQL REALES contra una base de datos SQLite en memoria.
  Los embeddings se almacenan como BLOBs (float32 empaquetados), equivalente a la
  columna VECTOR(1536) de pgvector. La búsqueda de similitud coseno se registra como
  función custom de SQLite (connection.create_function), replicando el operador <=>
  de pgvector.

  Mapeo de conceptos:
    SQLite TEXT          <-> PostgreSQL TEXT / VARCHAR
    SQLite BLOB          <-> PostgreSQL VECTOR(dim) de pgvector
    SQLite JSON (text)   <-> PostgreSQL JSONB
    create_function()    <-> Operador <=> de pgvector
    :memory:             <-> PostgreSQL con conexión TCP

  En producción, reemplazarías sqlite3 por asyncpg/psycopg y los BLOBs por columnas
  VECTOR reales con índices HNSW o IVFFlat.

Ejecución: uv run 01_python_frameworks/sqlite_openai_agents_demo.py
"""

import os
import math
import json
import struct
import sqlite3
import asyncio
from datetime import datetime, timezone

from agents import Agent, Runner, function_tool


# ==========================================
# 1. BASE DE DATOS SQLite REAL
# ==========================================

DIM = 8

SAMPLE_DOCS = [
    {
        "content": "PostgreSQL con pgvector unifica búsqueda vectorial y SQL relacional.",
        "category": "base_de_datos",
        "author": "karpathy",
        "embedding": [0.9, 0.8, 0.1, 0.05, 0.02, 0.01, 0.01, 0.01],
    },
    {
        "content": "Los índices HNSW aceleran consultas ANN en millones de filas.",
        "category": "indexacion",
        "author": "lecun",
        "embedding": [0.85, 0.75, 0.15, 0.1, 0.05, 0.03, 0.04, 0.03],
    },
    {
        "content": "Embeddings de OpenAI text-embedding-3-small: 1536 dimensiones.",
        "category": "embeddings",
        "author": "bengio",
        "embedding": [0.1, 0.05, 0.9, 0.8, 0.1, 0.02, 0.02, 0.01],
    },
    {
        "content": "RAG combina recuperación semántica con generación de texto por LLMs.",
        "category": "rag",
        "author": "karpathy",
        "embedding": [0.1, 0.1, 0.85, 0.7, 0.2, 0.02, 0.02, 0.01],
    },
    {
        "content": "El SDK de OpenAI Agents permite orquestar herramientas con handoffs.",
        "category": "agentes",
        "author": "hinton",
        "embedding": [0.05, 0.02, 0.1, 0.1, 0.9, 0.8, 0.02, 0.01],
    },
    {
        "content": "La normalización L2 de embeddings mejora la similitud coseno.",
        "category": "embeddings",
        "author": "lecun",
        "embedding": [0.15, 0.1, 0.8, 0.75, 0.05, 0.03, 0.08, 0.04],
    },
]


def _pack_embedding(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"{dim}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def create_database() -> sqlite3.Connection:
    """Crea una base SQLite en memoria con schema similar a pgvector."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")

    # En PostgreSQL: CREATE TABLE documents (
    #   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    #   content TEXT NOT NULL,
    #   embedding VECTOR(1536),       -- tipo nativo de pgvector
    #   metadata JSONB DEFAULT '{}',
    #   created_at TIMESTAMPTZ DEFAULT now()
    # );
    conn.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)

    # En PostgreSQL: CREATE INDEX ON documents
    #   USING hnsw (embedding vector_cosine_ops);
    # SQLite no soporta índices vectoriales nativos; la similitud se calcula en Python.
    conn.execute("""
        CREATE INDEX idx_documents_category
        ON documents(json_extract(metadata, '$.category'))
    """)

    now = datetime.now(timezone.utc).isoformat()
    for doc in SAMPLE_DOCS:
        meta = json.dumps({"category": doc["category"], "author": doc["author"]})
        conn.execute(
            "INSERT INTO documents (content, embedding, metadata, created_at) VALUES (?, ?, ?, ?)",
            (doc["content"], _pack_embedding(doc["embedding"]), meta, now),
        )

    conn.commit()

    def _sqlite_cosine_sim(blob_a, blob_b):
        if blob_a is None or blob_b is None:
            return 0.0
        vec_a = _unpack_embedding(blob_a, DIM)
        vec_b = _unpack_embedding(blob_b, DIM)
        return _cosine_similarity(vec_a, vec_b)

    # Equivalente al operador <=> de pgvector:
    #   SELECT *, embedding <=> '[0.1,0.2,...]' AS distance FROM documents
    #   ORDER BY distance LIMIT 5;
    conn.create_function("cosine_similarity", 2, _sqlite_cosine_sim)

    return conn


# ==========================================
# 2. HERRAMIENTAS CON @function_tool
# ==========================================

_db: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = create_database()
    return _db


def _get_table_schema(table_name: str) -> str:
    """Retorna el CREATE TABLE real de SQLite. En producción sería pg_catalog o information_schema de PostgreSQL."""
    print(f"   [Tool: get_table_schema] Consultando schema de '{table_name}'...")
    conn = _get_db()
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    if row is None:
        return f"Tabla '{table_name}' no encontrada."
    col_rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = []
    for cid, name, col_type, notnull, default, pk in col_rows:
        columns.append(f"  {name} {col_type} {'NOT NULL' if notnull else ''} {'PK' if pk else ''}".strip())
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return (
        f"Schema de '{table_name}' ({count} filas):\n"
        f"{row[0]}\n\n"
        f"Columnas:\n" + "\n".join(columns)
    )


def _query_documents(category: str = "", author: str = "", limit: int = 10) -> str:
    """Ejecuta un SELECT real con filtros WHERE sobre la tabla documents."""
    print(f"   [Tool: query_documents] category='{category}', author='{author}', limit={limit}...")
    conn = _get_db()
    conditions = []
    params: list[str] = []
    if category:
        conditions.append("json_extract(metadata, '$.category') = ?")
        params.append(category)
    if author:
        conditions.append("json_extract(metadata, '$.author') = ?")
        params.append(author)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(str(limit))
    rows = conn.execute(
        f"SELECT id, content, metadata, created_at FROM documents {where} LIMIT ?",
        params,
    ).fetchall()
    if not rows:
        return "No se encontraron documentos con esos filtros."
    lines = [f"Se encontraron {len(rows)} documento(s):"]
    for rid, content, meta, created in rows:
        m = json.loads(meta)
        lines.append(f"  [{rid}] cat={m.get('category')} author={m.get('author')} | {content[:80]}")
    return "\n".join(lines)


def _vector_search(query_embedding_json: str, top_k: int = 3) -> str:
    """
    Búsqueda de similitud coseno usando función custom de SQLite.
    En PostgreSQL+pgvector: SELECT *, embedding <=> query_vec AS distance
                            FROM documents ORDER BY distance LIMIT top_k;
    """
    print(f"   [Tool: vector_search] top_k={top_k}, calculando similitud coseno en SQL...")
    conn = _get_db()
    query_vec = json.loads(query_embedding_json)
    query_blob = _pack_embedding(query_vec)
    rows = conn.execute(
        """
        SELECT id, content, metadata,
               cosine_similarity(embedding, ?) AS similarity
        FROM documents
        WHERE embedding IS NOT NULL
        ORDER BY similarity DESC
        LIMIT ?
        """,
        (query_blob, top_k),
    ).fetchall()
    if not rows:
        return "No se encontraron resultados."
    lines = [f"Top {len(rows)} resultados (similitud coseno):"]
    for rid, content, meta, sim in rows:
        m = json.loads(meta)
        lines.append(f"  [{rid}] sim={sim:.4f} cat={m.get('category')} | {content[:70]}")
    return "\n".join(lines)


def _get_statistics() -> str:
    """Ejecuta queries de agregación reales: COUNT, AVG de longitud de contenido, etc."""
    print("   [Tool: get_statistics] Ejecutando queries de agregación...")
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    avg_len = conn.execute("SELECT AVG(LENGTH(content)) FROM documents").fetchone()[0]
    categories = conn.execute(
        "SELECT json_extract(metadata, '$.category'), COUNT(*) "
        "FROM documents GROUP BY json_extract(metadata, '$.category') ORDER BY COUNT(*) DESC"
    ).fetchall()
    authors = conn.execute(
        "SELECT json_extract(metadata, '$.author'), COUNT(*) "
        "FROM documents GROUP BY json_extract(metadata, '$.author') ORDER BY COUNT(*) DESC"
    ).fetchall()
    cat_lines = "\n".join(f"    {cat}: {cnt}" for cat, cnt in categories)
    auth_lines = "\n".join(f"    {auth}: {cnt}" for auth, cnt in authors)
    return (
        f"Estadísticas de la base de datos:\n"
        f"  Total de documentos: {total}\n"
        f"  Longitud promedio de contenido: {avg_len:.1f} caracteres\n"
        f"  Documentos por categoría:\n{cat_lines}\n"
        f"  Documentos por autor:\n{auth_lines}"
    )


get_table_schema = function_tool(_get_table_schema, name_override="get_table_schema")
query_documents = function_tool(_query_documents, name_override="query_documents")
vector_search = function_tool(_vector_search, name_override="vector_search")
get_statistics = function_tool(_get_statistics, name_override="get_statistics")


# ==========================================
# 3. DEFINICIÓN DEL AGENTE
# ==========================================

db_admin_agent = Agent(
    name="DB Admin Agent",
    instructions=(
        "Eres un agente administrador de bases de datos especializado en sistemas "
        "vectoriales. Podés inspeccionar schemas, consultar documentos, ejecutar "
        "búsquedas vectoriales por similitud coseno y obtener estadísticas. "
        "Usá las herramientas disponibles para responder con datos reales de la base. "
        "Siempre mostrá los resultados concretos que obtenés de las queries."
    ),
    tools=[get_table_schema, query_documents, vector_search, get_statistics],
)


# ==========================================
# 4. MODO MOCK (SIN API KEY, SQLite REAL)
# ==========================================

def run_mock_demo():
    """Ejecuta queries SQLite REALES pero simula las respuestas del LLM."""
    print("[NOTA] No se encontró OPENAI_API_KEY. Ejecutando con SQLite real + LLM simulado.\n")

    print("--- Paso 1: Creación de base de datos SQLite ---")
    conn = _get_db()
    print(f"  Base de datos creada en memoria con {DIM}-dimensional embeddings como BLOB.")
    print(f"  Equivalente PostgreSQL: tabla con columna VECTOR({DIM}) de pgvector.\n")

    print("--- Paso 2: Inspección de schema (query real) ---")
    result = _get_table_schema("documents")
    print(f"{result}\n")

    print("--- Paso 3: Consulta con filtros (query real) ---")
    print("  Filtro: category='embeddings'")
    result = _query_documents(category="embeddings")
    print(f"{result}\n")

    print("--- Paso 4: Búsqueda vectorial por similitud coseno (query real) ---")
    print("  Query embedding: [0.8, 0.7, 0.1, 0.05, 0.02, 0.01, 0.01, 0.01]")
    print("  Equivalente pgvector: SELECT *, embedding <=> '[0.8,...]' AS dist ... ORDER BY dist")
    query_emb = json.dumps([0.8, 0.7, 0.1, 0.05, 0.02, 0.01, 0.01, 0.01])
    result = _vector_search(query_emb, top_k=3)
    print(f"{result}\n")

    print("--- Paso 5: Estadísticas con agregaciones SQL (queries reales) ---")
    result = _get_statistics()
    print(f"{result}\n")

    print("--- Paso 6: Simulación del agente completo ---")
    print("  [Simulación] Usuario: 'Mostrame el schema y los documentos de embeddings'")
    print("  [DB Admin Agent] Invoco get_table_schema('documents')...")
    _get_table_schema("documents")
    print("  [DB Admin Agent] Invoco query_documents(category='embeddings')...")
    _query_documents(category="embeddings")
    print("  [DB Admin Agent] Acá tenés el schema y los documentos filtrados por categoría.\n")

    print("  [Simulación] Usuario: 'Buscá documentos similares a un embedding de RAG'")
    print("  [DB Admin Agent] Invoco vector_search() con embedding de consulta...")
    rag_emb = json.dumps([0.1, 0.1, 0.8, 0.7, 0.15, 0.02, 0.02, 0.01])
    _vector_search(rag_emb, top_k=3)
    print("  [DB Admin Agent] Los documentos más similares tratan sobre RAG y embeddings.\n")


# ==========================================
# 5. MODO REAL (CON API KEY, SQLite REAL)
# ==========================================

async def run_real_demo():
    """Ejecuta el agente real contra OpenAI con herramientas SQLite reales."""
    print("=== DB Admin Agent con OpenAI Agents SDK + SQLite Real ===\n")

    print("--- Paso 1: Inspección de schema ---")
    prompt = "Mostrame el schema de la tabla 'documents' y decime cuántos documentos hay."
    print(f"Pregunta: '{prompt}'")
    result = await Runner.run(db_admin_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")

    print("--- Paso 2: Consulta con filtros ---")
    prompt = "Buscá todos los documentos de la categoría 'embeddings' y mostrame qué encontraste."
    print(f"Pregunta: '{prompt}'")
    result = await Runner.run(db_admin_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")

    print("--- Paso 3: Búsqueda vectorial ---")
    query_emb = json.dumps([0.85, 0.75, 0.1, 0.05, 0.02, 0.01, 0.01, 0.01])
    prompt = (
        f"Buscá los 3 documentos más similares a este embedding: {query_emb}. "
        "Usá la herramienta vector_search y explicame los resultados."
    )
    print(f"Pregunta: '{prompt[:80]}...'")
    result = await Runner.run(db_admin_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")

    print("--- Paso 4: Estadísticas completas ---")
    prompt = "Dame un resumen estadístico completo de la base de datos: totales, categorías y autores."
    print(f"Pregunta: '{prompt}'")
    result = await Runner.run(db_admin_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")


# ==========================================
# ENTRY POINT
# ==========================================

def run_demo():
    print("==========================================================")
    print("  SQLite + OpenAI Agents SDK - DB Admin Agent")
    print("  (SQLite como stand-in de PostgreSQL+pgvector)")
    print("==========================================================\n")

    api_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        asyncio.run(run_real_demo())
    else:
        run_mock_demo()

    print("==========================================================")
    print("  Fin de la demostración")
    print("==========================================================")


if __name__ == "__main__":
    run_demo()
