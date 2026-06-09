# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.27.2",
# ]
# ///
"""
sqlite_mcp_server_demo.py

Demostración de un MCP Server REAL conectado a SQLite como backend de datos.

A diferencia de mcp_demo.py (que usa datos mock), este servidor ejecuta
consultas SQL reales contra una base de datos SQLite con datos de ejemplo
sobre ingeniería de IA.

El esquema replica la estructura típica de un sistema RAG con pgvector:
- Tabla de documentos con embeddings (almacenados como JSON en SQLite)
- Búsqueda full-text con FTS5 (análogo a pg_trgm en PostgreSQL)
- Similitud coseno calculada en Python (análogo a <=> en pgvector)
- Metadata JSONB simulada con columna TEXT + json.loads()

En producción, este mismo patrón se aplica con:
- PostgreSQL + pgvector en lugar de SQLite
- VECTOR(1536) en lugar de JSON para embeddings
- Índices HNSW/IVFFlat para búsqueda vectorial eficiente
- pg_trgm + GIN para búsqueda full-text

Ejecución demo:     uv run 01_python_frameworks/sqlite_mcp_server_demo.py
Ejecución servidor: uv run 01_python_frameworks/sqlite_mcp_server_demo.py --serve
"""

import sys
import json
import math
import sqlite3
import tempfile
import os
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP


# ==========================================
# INICIALIZACIÓN DE BASE DE DATOS
# ==========================================

DB_PATH = os.path.join(tempfile.gettempdir(), "ai_engineering_lab.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT    NOT NULL,
            embedding   TEXT,
            metadata    TEXT    DEFAULT '{}',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            content,
            content='documents',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
        END;
    """)

    existing = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if existing == 0:
        sample_docs = [
            (
                "RAG (Retrieval-Augmented Generation) combina búsqueda vectorial con "
                "generación de texto. Los documentos se indexan como embeddings en pgvector "
                "y se recuperan los top-k más relevantes antes de pasarlos al LLM.",
                json.dumps([0.12, 0.85, 0.33, 0.67, 0.21, 0.91, 0.45, 0.78]),
                json.dumps({"topic": "rag", "difficulty": "intermediate", "tags": ["retrieval", "embeddings"]}),
            ),
            (
                "Los embeddings son representaciones vectoriales densas de texto. "
                "Modelos como text-embedding-3-small de OpenAI generan vectores de 1536 "
                "dimensiones que capturan semántica del lenguaje natural.",
                json.dumps([0.15, 0.82, 0.30, 0.70, 0.18, 0.88, 0.42, 0.75]),
                json.dumps({"topic": "embeddings", "difficulty": "beginner", "tags": ["vectors", "openai"]}),
            ),
            (
                "pgvector es la extensión de PostgreSQL para búsqueda vectorial. "
                "Soporta índices HNSW e IVFFlat para acelerar consultas de similitud "
                "coseno sobre millones de documentos.",
                json.dumps([0.10, 0.88, 0.35, 0.65, 0.25, 0.93, 0.40, 0.80]),
                json.dumps({"topic": "pgvector", "difficulty": "advanced", "tags": ["postgres", "indexing"]}),
            ),
            (
                "El fine-tuning adapta un modelo base a un dominio específico usando "
                "datos etiquetados. Es útil cuando el prompting no alcanza para lograr "
                "el comportamiento deseado en tareas especializadas.",
                json.dumps([0.55, 0.30, 0.72, 0.15, 0.60, 0.25, 0.80, 0.10]),
                json.dumps({"topic": "fine-tuning", "difficulty": "advanced", "tags": ["training", "adaptation"]}),
            ),
            (
                "Los agentes de IA usan tool-calling para interactuar con APIs externas. "
                "Frameworks como LangGraph y Pydantic AI permiten construir flujos "
                "multi-paso con planificación y memoria a largo plazo.",
                json.dumps([0.60, 0.25, 0.75, 0.10, 0.65, 0.20, 0.85, 0.05]),
                json.dumps({"topic": "agents", "difficulty": "intermediate", "tags": ["langgraph", "tool-calling"]}),
            ),
            (
                "La búsqueda full-text con BM25 rankea documentos por frecuencia de "
                "términos inversa. En PostgreSQL se usa tsvector/tsquery; en SQLite "
                "se usa FTS5. Ambos soportan operadores AND, OR y NOT.",
                json.dumps([0.18, 0.80, 0.28, 0.72, 0.15, 0.85, 0.48, 0.70]),
                json.dumps({"topic": "full-text-search", "difficulty": "beginner", "tags": ["bm25", "fts5"]}),
            ),
            (
                "MCP (Model Context Protocol) estandariza cómo los LLMs acceden a "
                "herramientas y datos externos. Un servidor MCP expone tools y resources "
                "que cualquier cliente compatible puede consumir.",
                json.dumps([0.40, 0.50, 0.55, 0.40, 0.50, 0.55, 0.60, 0.45]),
                json.dumps({"topic": "mcp", "difficulty": "intermediate", "tags": ["protocol", "tools"]}),
            ),
        ]

        cur.executemany(
            "INSERT INTO documents (content, embedding, metadata) VALUES (?, ?, ?)",
            sample_docs,
        )

    conn.commit()
    conn.close()


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except json.JSONDecodeError:
            pass
    return d


# ==========================================
# DEFINICIÓN DEL MCP SERVER
# ==========================================

mcp = FastMCP("sqlite-ai-lab")


@mcp.tool()
def list_tables() -> list[str]:
    """Lista todas las tablas reales en la base de datos SQLite.
    En producción con PostgreSQL, esto consultaría information_schema.tables."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


@mcp.tool()
def get_schema(table_name: str) -> str:
    """Retorna el DDL CREATE TABLE real de una tabla SQLite.
    En producción con PostgreSQL, esto consultaría pg_catalog o information_schema."""
    conn = get_connection()
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    conn.close()
    if row is None:
        return f"Error: la tabla '{table_name}' no existe."
    return row["sql"]


@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """Búsqueda full-text real usando FTS5 (análogo a pg_trgm/tsvector en PostgreSQL).
    Retorna los documentos más relevantes rankeados por BM25."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT d.id, d.content, d.metadata, d.created_at,
               rank AS relevance_score
        FROM documents_fts fts
        JOIN documents d ON d.id = fts.rowid
        WHERE documents_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, top_k),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        doc = row_to_dict(r)
        doc["relevance_score"] = round(abs(doc["relevance_score"]), 4)
        results.append(doc)
    return results


@mcp.tool()
def vector_search(embedding_json: str, top_k: int = 5) -> list[dict]:
    """Búsqueda por similitud coseno real contra embeddings almacenados.
    En producción con pgvector, esto sería: SELECT ... ORDER BY embedding <=> $1 LIMIT $2
    con índice HNSW para consultas en sub-milisegundos sobre millones de vectores."""
    try:
        query_vec = json.loads(embedding_json)
    except json.JSONDecodeError:
        return [{"error": "embedding_json debe ser un array JSON válido de floats."}]

    conn = get_connection()
    rows = conn.execute("SELECT id, content, embedding, metadata, created_at FROM documents").fetchall()
    conn.close()

    scored = []
    for r in rows:
        doc = row_to_dict(r)
        try:
            doc_vec = json.loads(r["embedding"]) if r["embedding"] else []
        except json.JSONDecodeError:
            doc_vec = []
        score = cosine_similarity(query_vec, doc_vec)
        doc["similarity_score"] = round(score, 4)
        del doc["embedding"]
        scored.append(doc)

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]


@mcp.tool()
def insert_document(content: str, metadata: str = "{}") -> dict:
    """Inserta un documento real en la base de datos SQLite.
    El trigger propaga automáticamente el contenido a la tabla FTS5.
    En producción con PostgreSQL, el embedding se generaría con un modelo
    antes del INSERT: embedding = model.encode(content)."""
    try:
        meta_parsed = json.loads(metadata)
    except json.JSONDecodeError:
        return {"error": "metadata debe ser un objeto JSON válido."}

    placeholder_embedding = json.dumps([0.0] * 8)

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO documents (content, embedding, metadata) VALUES (?, ?, ?)",
        (content, placeholder_embedding, json.dumps(meta_parsed)),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return {
        "status": "inserted",
        "id": new_id,
        "content_preview": content[:80] + ("..." if len(content) > 80 else ""),
        "metadata": meta_parsed,
    }


@mcp.tool()
def get_stats() -> dict:
    """Retorna estadísticas reales de la base de datos: conteos, tamaños y distribución.
    En producción con PostgreSQL, esto usaría pg_stat_user_tables y pg_total_relation_size."""
    conn = get_connection()

    doc_count = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]

    topic_counts = conn.execute(
        """
        SELECT json_extract(metadata, '$.topic') AS topic, COUNT(*) AS count
        FROM documents
        GROUP BY topic
        ORDER BY count DESC
        """
    ).fetchall()

    difficulty_counts = conn.execute(
        """
        SELECT json_extract(metadata, '$.difficulty') AS difficulty, COUNT(*) AS count
        FROM documents
        GROUP BY difficulty
        ORDER BY count DESC
        """
    ).fetchall()

    avg_content_len = conn.execute(
        "SELECT AVG(LENGTH(content)) AS avg_len FROM documents"
    ).fetchone()["avg_len"]

    oldest = conn.execute("SELECT MIN(created_at) AS ts FROM documents").fetchone()["ts"]
    newest = conn.execute("SELECT MAX(created_at) AS ts FROM documents").fetchone()["ts"]

    conn.close()

    return {
        "total_documents": doc_count,
        "avg_content_length": round(avg_content_len, 1) if avg_content_len else 0,
        "topics": {r["topic"]: r["count"] for r in topic_counts},
        "difficulty_distribution": {r["difficulty"]: r["count"] for r in difficulty_counts},
        "date_range": {"oldest": oldest, "newest": newest},
        "database_path": DB_PATH,
    }


@mcp.resource("db://schema")
def db_schema_resource() -> str:
    """Esquema completo de la base de datos como recurso MCP."""
    conn = get_connection()
    tables = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    parts = [f"-- Base de datos: {DB_PATH}\n"]
    for t in tables:
        parts.append(f"-- Tabla: {t['name']}")
        parts.append(t["sql"] + ";\n")
    return "\n".join(parts)


@mcp.resource("db://stats")
def db_stats_resource() -> str:
    """Estadísticas de la base de datos como recurso MCP."""
    return json.dumps(get_stats(), indent=2, ensure_ascii=False)


# ==========================================
# MODO DEMO (llamadas directas sin transporte MCP)
# ==========================================

def run_demo():
    print("==========================================================")
    print("  MCP + SQLite — Servidor REAL con base de datos")
    print("==========================================================")

    print("\n--- Paso 1: Inicializando base de datos SQLite ---")
    init_database()
    print(f"   Base de datos creada en: {DB_PATH}")

    print("\n--- Paso 2: list_tables() ---")
    tables = list_tables()
    print(f"   Tablas encontradas: {tables}")

    print("\n--- Paso 3: get_schema('documents') ---")
    schema = get_schema("documents")
    print(f"   DDL:\n   {schema}")

    print("\n--- Paso 4: search_documents('embeddings vectorial', top_k=3) ---")
    results = search_documents("embeddings vectorial", top_k=3)
    if results:
        for r in results:
            print(f"   [id={r['id']}] score={r['relevance_score']}")
            print(f"      {r['content'][:90]}...")
    else:
        print("   Sin resultados.")

    print("\n--- Paso 5: vector_search() con embedding de consulta ---")
    query_embedding = json.dumps([0.13, 0.84, 0.32, 0.68, 0.20, 0.90, 0.44, 0.77])
    vec_results = vector_search(query_embedding, top_k=3)
    for r in vec_results:
        print(f"   [id={r['id']}] similitud={r['similarity_score']}")
        print(f"      topic={r['metadata'].get('topic', '?')}")
        print(f"      {r['content'][:90]}...")

    print("\n--- Paso 6: insert_document() ---")
    insert_result = insert_document(
        content=(
            "Chunking es la técnica de dividir documentos largos en fragmentos "
            "más pequeños para mejorar la relevancia en RAG. Estrategias comunes "
            "incluyen chunking por tokens, por oraciones y por párrafos."
        ),
        metadata=json.dumps({"topic": "chunking", "difficulty": "beginner", "tags": ["rag", "preprocessing"]}),
    )
    print(f"   Resultado: {json.dumps(insert_result, indent=2, ensure_ascii=False)}")

    print("\n--- Paso 7: get_stats() ---")
    stats = get_stats()
    print(f"   Total documentos: {stats['total_documents']}")
    print(f"   Largo promedio:   {stats['avg_content_length']} chars")
    print(f"   Temas:            {stats['topics']}")
    print(f"   Dificultad:       {stats['difficulty_distribution']}")

    print("\n--- Paso 8: Recurso db://schema ---")
    schema_res = db_schema_resource()
    for line in schema_res.split("\n")[:8]:
        print(f"   {line}")
    print("   ...")

    print("\n==========================================================")
    print("  Conexión con producción (PostgreSQL + pgvector):")
    print("  - SQLite FTS5     -> PostgreSQL tsvector + pg_trgm")
    print("  - JSON embeddings -> VECTOR(1536) con índice HNSW")
    print("  - json_extract()  -> JSONB operators @>, ->>")
    print("  - cosine_similarity() -> operador <=> de pgvector")
    print("  - Este mismo patrón MCP escala a cualquier backend")
    print("==========================================================")
    print("  Ejecuta con --serve para iniciar como servidor MCP real.")
    print("==========================================================")


# ==========================================
# MODO SERVIDOR MCP
# ==========================================

def run_server():
    init_database()
    mcp.run()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        run_demo()
