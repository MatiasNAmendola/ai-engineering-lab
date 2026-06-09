# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.0.0",
# ]
# ///
"""
mcp_demo.py

Demostración del Model Context Protocol (MCP), el estándar abierto para que
los modelos de IA consuman datos y expongan herramientas de forma uniforme.

MCP utiliza una arquitectura cliente-servidor:
- MCP Server: Expone herramientas (tools) y recursos (resources) — por ejemplo,
  acceso a bases de datos, sistema de archivos o APIs externas.
- MCP Client: Runtime del agente de IA que se conecta a servidores MCP y
  consume sus herramientas de forma estandarizada.

Este archivo demuestra ambas caras:
1. Definición de un MCP Server con FastMCP (tools + resources).
2. Simulación de un cliente que consume las herramientas del servidor.

Ejecución: uv run 01_python_frameworks/mcp_demo.py
Ejecución como servidor MCP real: uv run 01_python_frameworks/mcp_demo.py --serve
"""

import sys
import json
from mcp.server.fastmcp import FastMCP


# ==========================================
# DEFINICIÓN DEL MCP SERVER
# ==========================================

mcp = FastMCP("ai-engineering-lab")


@mcp.tool()
def get_table_schema(table_name: str) -> dict:
    """Obtiene el esquema de una tabla en PostgreSQL."""
    schemas = {
        "documents": {
            "table": "documents",
            "columns": [
                {"name": "id", "type": "UUID", "nullable": False},
                {"name": "content", "type": "TEXT", "nullable": False},
                {"name": "embedding", "type": "VECTOR(1536)", "nullable": True},
                {"name": "metadata", "type": "JSONB", "nullable": True},
                {"name": "created_at", "type": "TIMESTAMPTZ", "nullable": False},
            ],
        },
        "users": {
            "table": "users",
            "columns": [
                {"name": "id", "type": "UUID", "nullable": False},
                {"name": "email", "type": "VARCHAR(255)", "nullable": False},
                {"name": "preferences", "type": "JSONB", "nullable": True},
                {"name": "created_at", "type": "TIMESTAMPTZ", "nullable": False},
            ],
        },
    }
    return schemas.get(table_name, {"error": f"Tabla '{table_name}' no encontrada."})


@mcp.tool()
def vector_search(query: str, top_k: int = 5) -> list[dict]:
    """Busca documentos similares usando pgvector y similitud coseno."""
    results = [
        {"id": "doc-001", "score": 0.95, "content": f"Resultado relevante para: '{query}'"},
        {"id": "doc-002", "score": 0.87, "content": "Documento relacionado con embeddings y RAG."},
        {"id": "doc-003", "score": 0.82, "content": "Guía de indexación vectorial en PostgreSQL."},
    ]
    return results[:top_k]


@mcp.tool()
def execute_query(sql: str) -> dict:
    """Ejecuta una consulta SQL de solo lectura en PostgreSQL."""
    return {
        "status": "success",
        "rows_affected": 0,
        "result": [{"count": 1024, "table": "documents"}],
        "note": "Modo lectura — solo SELECT permitido.",
    }


@mcp.resource("config://database")
def get_database_config() -> str:
    """Configuración de conexión a PostgreSQL."""
    return json.dumps({
        "host": "127.0.0.1",
        "port": 5432,
        "database": "ai_lab",
        "extensions": ["pgvector", "pg_trgm"],
    })


@mcp.resource("status://system")
def get_system_status() -> str:
    """Estado actual del sistema de base de datos."""
    return json.dumps({
        "postgres": "healthy",
        "pgvector": "active",
        "connections": 12,
        "max_connections": 100,
    })


# ==========================================
# SIMULACIÓN DEL CLIENTE MCP
# ==========================================

def run_client_demo():
    print("==========================================================")
    print("🔌 MCP DEMO — Model Context Protocol")
    print("==========================================================")

    print("\n🟢 1. MCP SERVER (Definición de herramientas y recursos)")
    print("   - Servidor: 'ai-engineering-lab'")
    print("   - Herramientas registradas: get_table_schema, vector_search, execute_query")
    print("   - Recursos registrados: config://database, status://system")

    print("\n🟢 2. MCP CLIENT (Consumo de herramientas del servidor)")
    print("   - Simulando conexión del cliente al servidor MCP...")

    print("\n--- Llamando tool: get_table_schema('documents') ---")
    schema = get_table_schema("documents")
    print(f"   Resultado: {json.dumps(schema, indent=2)}")

    print("\n--- Llamando tool: vector_search('embeddings en postgres') ---")
    results = vector_search("embeddings en postgres", top_k=3)
    for r in results:
        print(f"   [{r['id']}] score={r['score']} — {r['content']}")

    print("\n--- Llamando tool: execute_query('SELECT count(*) FROM documents') ---")
    query_result = execute_query("SELECT count(*) FROM documents")
    print(f"   Resultado: {json.dumps(query_result, indent=2)}")

    print("\n--- Leyendo recurso: config://database ---")
    config = get_database_config()
    print(f"   {config}")

    print("\n--- Leyendo recurso: status://system ---")
    status = get_system_status()
    print(f"   {status}")

    print("\n🟢 3. INTEGRACIÓN CON LANGCHAIN (langchain-mcp-adapters)")
    print("   - Para conectar este servidor MCP con un agente LangChain:")
    print("""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async with MultiServerMCPClient({
        "ai_lab": {
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "01_python_frameworks/mcp_demo.py", "--serve"],
        }
    }) as client:
        tools = await client.get_tools()
        # tools ahora contiene get_table_schema, vector_search, execute_query
        # Listos para usar con cualquier agente de LangChain/LangGraph
    """)

    print("==========================================================")
    print("✅ Demo completada. Ejecuta con --serve para iniciar el servidor MCP real.")
    print("==========================================================")


# ==========================================
# MODO SERVIDOR MCP
# ==========================================

def run_server():
    print("🚀 Iniciando MCP Server 'ai-engineering-lab'...")
    print("   Transporte: stdio")
    print("   Herramientas: get_table_schema, vector_search, execute_query")
    print("   Recursos: config://database, status://system")
    mcp.run()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        run_client_demo()
