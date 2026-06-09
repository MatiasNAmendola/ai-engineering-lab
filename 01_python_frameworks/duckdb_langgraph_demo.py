# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.0.0",
#     "langgraph>=1.2.4",
#     "langchain>=1.3.4",
#     "langchain-google-genai>=4.2.4",
# ]
# ///
"""
duckdb_langgraph_demo.py

Integración de DuckDB (base de datos analítica en proceso) con LangGraph (framework de agentes).
Demuestra cómo un agente de IA puede razonar sobre datos reales almacenados en DuckDB,
ejecutando consultas SQL reales para análisis de embeddings, documentos y métricas de búsqueda vectorial.

Arquitectura:
- DuckDB: Motor analítico en memoria, sin servidor, ideal para datos estructurados y vectoriales.
- LangGraph: Orquesta el flujo del agente con estado, herramientas y bucles de decisión ReAct.
- LangChain: Unifica la interfaz con el LLM (Gemini) y estructura los mensajes.

Ejecución: uv run 01_python_frameworks/duckdb_langgraph_demo.py
"""

import os
import json
import math
from typing import TypedDict, Annotated, Sequence
import duckdb
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver


# ==========================================
# INICIALIZACIÓN DE DUCKDB CON DATOS REALES
# ==========================================

def create_analytics_database() -> duckdb.DuckDBPyConnection:
    """Crea una base de datos DuckDB en memoria con datos de analytics de IA."""
    conn = duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title VARCHAR,
            category VARCHAR,
            content_length INTEGER,
            embedding_dim INTEGER,
            created_at DATE,
            chunk_count INTEGER,
            avg_token_length DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE embeddings (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            model VARCHAR,
            dimensions INTEGER,
            vector_norm DOUBLE,
            inference_time_ms DOUBLE,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)

    conn.execute("""
        CREATE TABLE search_queries (
            id INTEGER PRIMARY KEY,
            query_text VARCHAR,
            top_k INTEGER,
            results_count INTEGER,
            latency_ms DOUBLE,
            cosine_threshold DOUBLE,
            timestamp TIMESTAMP
        )
    """)

    conn.execute("""
        INSERT INTO documents VALUES
            (1, 'Introducción a RAG', 'tutorial', 2500, 768, '2024-01-15', 12, 45.2),
            (2, 'Embeddings con Sentence-Transformers', 'tutorial', 3200, 384, '2024-01-20', 15, 52.1),
            (3, 'Arquitectura de Vector DB', 'arquitectura', 4800, 1536, '2024-02-01', 22, 67.8),
            (4, 'Optimización de Índices HNSW', 'performance', 5100, 768, '2024-02-10', 18, 71.3),
            (5, 'Fine-tuning de Modelos', 'ml-ops', 3800, 1024, '2024-02-15', 16, 58.9),
            (6, 'Chunking Strategies', 'tutorial', 2900, 768, '2024-03-01', 14, 48.5),
            (7, 'Evaluación de Retrieval', 'evaluacion', 4200, 1536, '2024-03-10', 20, 63.2),
            (8, 'Prompt Engineering Avanzado', 'tutorial', 3500, 768, '2024-03-15', 17, 55.7),
            (9, 'Deploy de Modelos en Producción', 'ml-ops', 4600, 1024, '2024-03-20', 21, 69.1),
            (10, 'Seguridad en APIs de IA', 'seguridad', 3100, 768, '2024-04-01', 13, 50.4)
    """)

    conn.execute("""
        INSERT INTO embeddings VALUES
            (1, 1, 'all-MiniLM-L6-v2', 384, 12.45, 45.2),
            (2, 1, 'text-embedding-3-small', 1536, 28.91, 120.5),
            (3, 2, 'all-MiniLM-L6-v2', 384, 11.82, 42.1),
            (4, 3, 'text-embedding-3-large', 1536, 31.24, 185.3),
            (5, 4, 'all-MiniLM-L6-v2', 384, 13.01, 48.7),
            (6, 5, 'bge-large-en', 1024, 22.67, 95.4),
            (7, 6, 'all-MiniLM-L6-v2', 384, 12.18, 44.8),
            (8, 7, 'text-embedding-3-large', 1536, 30.55, 178.2),
            (9, 8, 'all-MiniLM-L6-v2', 384, 12.89, 46.3),
            (10, 9, 'bge-large-en', 1024, 23.41, 98.7),
            (11, 10, 'all-MiniLM-L6-v2', 384, 11.95, 43.9)
    """)

    conn.execute("""
        INSERT INTO search_queries VALUES
            (1, 'cómo funciona RAG', 5, 5, 23.4, 0.75, '2024-04-01 10:30:00'),
            (2, 'optimización de índices', 10, 8, 45.2, 0.80, '2024-04-01 11:15:00'),
            (3, 'estrategias de chunking', 5, 5, 21.8, 0.70, '2024-04-02 09:00:00'),
            (4, 'modelos de embedding', 10, 10, 52.1, 0.85, '2024-04-02 14:30:00'),
            (5, 'deploy en producción', 5, 4, 28.9, 0.75, '2024-04-03 16:45:00'),
            (6, 'evaluación retrieval', 5, 5, 25.3, 0.72, '2024-04-04 10:00:00'),
            (7, 'seguridad APIs', 3, 3, 18.7, 0.68, '2024-04-05 11:30:00'),
            (8, 'fine-tuning LLM', 10, 7, 48.6, 0.82, '2024-04-06 13:20:00')
    """)

    return conn


# ==========================================
# HERRAMIENTAS DE CONSULTA SQL (TOOLS)
# ==========================================

def count_documents_by_category(conn: duckdb.DuckDBPyConnection) -> str:
    """Cuenta documentos agrupados por categoría."""
    result = conn.execute("""
        SELECT category, COUNT(*) as total, 
               ROUND(AVG(content_length), 0) as avg_length,
               SUM(chunk_count) as total_chunks
        FROM documents 
        GROUP BY category 
        ORDER BY total DESC
    """).fetchall()

    output = ["Documentos por categoría:"]
    for row in result:
        output.append(f"  - {row[0]}: {row[1]} docs, largo promedio {row[2]} chars, {row[3]} chunks totales")
    return "\n".join(output)


def get_embedding_statistics(conn: duckdb.DuckDBPyConnection) -> str:
    """Obtiene estadísticas de los modelos de embedding utilizados."""
    result = conn.execute("""
        SELECT model, 
               COUNT(*) as usage_count,
               dimensions,
               ROUND(AVG(vector_norm), 2) as avg_norm,
               ROUND(AVG(inference_time_ms), 1) as avg_inference_ms
        FROM embeddings 
        GROUP BY model, dimensions
        ORDER BY usage_count DESC
    """).fetchall()

    output = ["Estadísticas de modelos de embedding:"]
    for row in result:
        output.append(f"  - {row[0]} ({row[2]}d): {row[1]} usos, norma promedio {row[3]}, inferencia {row[4]}ms")
    return "\n".join(output)


def get_search_performance(conn: duckdb.DuckDBPyConnection) -> str:
    """Analiza el rendimiento de las búsquedas vectoriales."""
    result = conn.execute("""
        SELECT 
            COUNT(*) as total_queries,
            ROUND(AVG(latency_ms), 1) as avg_latency,
            ROUND(AVG(results_count), 1) as avg_results,
            ROUND(AVG(cosine_threshold), 2) as avg_threshold,
            MAX(latency_ms) as max_latency,
            MIN(latency_ms) as min_latency
        FROM search_queries
    """).fetchone()

    return f"""Rendimiento de búsqueda vectorial:
  - Total de consultas: {result[0]}
  - Latencia promedio: {result[1]}ms (min: {result[5]}ms, max: {result[4]}ms)
  - Resultados promedio por consulta: {result[2]}
  - Umbral coseno promedio: {result[3]}"""


def find_top_similar_documents(conn: duckdb.DuckDBPyConnection, category: str, limit: int = 3) -> str:
    """Encuentra documentos similares basado en categoría y métricas."""
    result = conn.execute("""
        SELECT d.title, d.category, d.content_length, d.chunk_count,
               e.model, e.dimensions, e.vector_norm
        FROM documents d
        JOIN embeddings e ON d.id = e.document_id
        WHERE d.category = ?
        ORDER BY d.content_length DESC
        LIMIT ?
    """, [category, limit]).fetchall()

    if not result:
        return f"No se encontraron documentos en la categoría '{category}'."

    output = [f"Top {limit} documentos en categoría '{category}':"]
    for row in result:
        output.append(f"  - '{row[0]}' ({row[4]}, {row[5]}d): {row[2]} chars, {row[3]} chunks, norma {row[6]:.2f}")
    return "\n".join(output)


def get_dataset_overview(conn: duckdb.DuckDBPyConnection) -> str:
    """Obtiene un resumen general del dataset."""
    docs = conn.execute("SELECT COUNT(*), SUM(chunk_count), AVG(embedding_dim) FROM documents").fetchone()
    embeds = conn.execute("SELECT COUNT(*), COUNT(DISTINCT model) FROM embeddings").fetchone()
    queries = conn.execute("SELECT COUNT(*), AVG(latency_ms) FROM search_queries").fetchone()

    return f"""Resumen del dataset de analytics:
  - Documentos: {docs[0]} totales, {docs[1]} chunks, dimensión embedding promedio {docs[2]:.0f}
  - Embeddings: {embeds[0]} registros de {embeds[1]} modelos diferentes
  - Consultas de búsqueda: {queries[0]} ejecutadas, latencia promedio {queries[1]:.1f}ms"""


# ==========================================
# ESTADO DEL AGENTE Y NODOS DEL GRAFO
# ==========================================

class AnalyticsAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query_results: list


def create_tool_node(conn: duckdb.DuckDBPyConnection):
    """Crea el nodo de herramientas con acceso a la conexión DuckDB."""

    def tool_executor(state: AnalyticsAgentState):
        """Ejecuta la herramienta solicitada por el agente."""
        last_message = state["messages"][-1]

        if not hasattr(last_message, "additional_kwargs") or "tool_calls" not in last_message.additional_kwargs:
            return {"messages": []}

        tool_call = last_message.additional_kwargs["tool_calls"][0]
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})

        print(f"\n   [Tool: {tool_name}] Ejecutando consulta SQL en DuckDB...")

        if tool_name == "count_by_category":
            result = count_documents_by_category(conn)
        elif tool_name == "embedding_stats":
            result = get_embedding_statistics(conn)
        elif tool_name == "search_performance":
            result = get_search_performance(conn)
        elif tool_name == "similar_documents":
            category = tool_args.get("category", "tutorial")
            limit = tool_args.get("limit", 3)
            result = find_top_similar_documents(conn, category, limit)
        elif tool_name == "dataset_overview":
            result = get_dataset_overview(conn)
        else:
            result = f"Herramienta desconocida: {tool_name}"

        print(f"   [Tool: {tool_name}] Resultado obtenido de DuckDB")

        tool_message = ToolMessage(content=result, tool_call_id=tool_call.get("id", "call_1"))
        return {"messages": [tool_message], "query_results": [result]}

    return tool_executor


def create_agent_node(conn: duckdb.DuckDBPyConnection):
    """Crea el nodo del agente LLM."""

    def agent_executor(state: AnalyticsAgentState):
        """Nodo del LLM que razona sobre los datos."""
        messages = state["messages"]
        api_key = os.environ.get("GEMINI_API_KEY")

        system_prompt = """Eres un analista de datos especializado en sistemas de IA y búsqueda vectorial.
Tienes acceso a una base de datos DuckDB con información sobre documentos, embeddings y consultas de búsqueda.

Herramientas disponibles:
- count_by_category: Cuenta documentos por categoría
- embedding_stats: Estadísticas de modelos de embedding
- search_performance: Rendimiento de búsquedas vectoriales
- similar_documents(category, limit): Documentos similares por categoría
- dataset_overview: Resumen general del dataset

Analiza las preguntas del usuario y usa las herramientas para obtener datos reales de DuckDB."""

        if api_key:
            model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key,
                temperature=0
            )

            full_messages = [HumanMessage(content=system_prompt)] + list(messages)
            response = model.invoke(full_messages)
            return {"messages": [response]}
        else:
            print("\n[NOTE] Sin GEMINI_API_KEY. Usando razonamiento simulado con consultas DuckDB reales.")

            last_message = messages[-1]

            if isinstance(last_message, ToolMessage):
                final_response = AIMessage(
                    content=f"Aquí están los resultados de la consulta DuckDB:\n\n{last_message.content}"
                )
                return {"messages": [final_response]}

            user_text = last_message.content.lower() if hasattr(last_message, 'content') else ""

            if "categoría" in user_text or "category" in user_text or "documento" in user_text:
                mock_response = AIMessage(
                    content="Voy a consultar la distribución de documentos por categoría en DuckDB.",
                    additional_kwargs={"tool_calls": [{"name": "count_by_category", "args": {}, "id": "call_1"}]}
                )
            elif "embedding" in user_text or "modelo" in user_text:
                mock_response = AIMessage(
                    content="Consultaré las estadísticas de los modelos de embedding.",
                    additional_kwargs={"tool_calls": [{"name": "embedding_stats", "args": {}, "id": "call_2"}]}
                )
            elif "rendimiento" in user_text or "performance" in user_text or "búsqueda" in user_text:
                mock_response = AIMessage(
                    content="Analizaré el rendimiento de las búsquedas vectoriales.",
                    additional_kwargs={"tool_calls": [{"name": "search_performance", "args": {}, "id": "call_3"}]}
                )
            elif "similar" in user_text or "tutorial" in user_text:
                mock_response = AIMessage(
                    content="Buscaré documentos similares en la categoría solicitada.",
                    additional_kwargs={"tool_calls": [{"name": "similar_documents", "args": {"category": "tutorial", "limit": 3}, "id": "call_4"}]}
                )
            elif "resumen" in user_text or "overview" in user_text or "dataset" in user_text:
                mock_response = AIMessage(
                    content="Obtendré un resumen general del dataset.",
                    additional_kwargs={"tool_calls": [{"name": "dataset_overview", "args": {}, "id": "call_5"}]}
                )
            else:
                mock_response = AIMessage(
                    content="Basándome en los datos de DuckDB, el sistema contiene documentos de múltiples categorías con embeddings de diferentes modelos. ¿Qué aspecto te gustaría analizar en detalle?"
                )

            return {"messages": [mock_response]}

    return agent_executor


def should_continue(state: AnalyticsAgentState):
    """Decide si el agente debe continuar consultando herramientas."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "additional_kwargs") and "tool_calls" in last_message.additional_kwargs:
        return "continue"
    return "end"


# ==========================================
# DEMOSTRACIÓN PRINCIPAL
# ==========================================

def run_duckdb_langgraph_demo():
    print("=" * 70)
    print("  DUCKDB + LANGGRAPH: Agente de Analytics para Sistemas de IA")
    print("=" * 70)

    print("\n--- Paso 1: Inicializando base de datos DuckDB en memoria ---")
    conn = create_analytics_database()
    print("   Base de datos DuckDB creada con tablas: documents, embeddings, search_queries")

    print("\n--- Paso 2: Verificando datos cargados ---")
    overview = get_dataset_overview(conn)
    print(overview)

    print("\n--- Paso 3: Construyendo grafo de LangGraph ---")

    workflow = StateGraph(AnalyticsAgentState)

    agent_node = create_agent_node(conn)
    tool_node = create_tool_node(conn)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END}
    )
    workflow.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    print("   Grafo compilado con nodos: agent, tools")

    print("\n--- Paso 4: Ejecutando consultas del agente ---")

    queries = [
        ("¿Cuántos documentos hay por categoría?", "thread_1"),
        ("¿Qué modelos de embedding se usan y cuál es su rendimiento?", "thread_2"),
        ("Muéstrame el rendimiento de las búsquedas vectoriales", "thread_3"),
        ("Dame un resumen general del dataset", "thread_4"),
    ]

    for query, thread_id in queries:
        print(f"\n{'─' * 60}")
        print(f"Pregunta: {query}")
        print(f"{'─' * 60}")

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}
        inputs = {
            "messages": [HumanMessage(content=query)],
            "query_results": []
        }

        for output in app.stream(inputs, config=config):
            for node_name, value in output.items():
                print(f"\n[Nodo: {node_name}]")
                for msg in value.get("messages", []):
                    if isinstance(msg, AIMessage):
                        print(f"  Agente: {msg.content}")
                    elif isinstance(msg, ToolMessage):
                        print(f"  Resultado DuckDB:\n{msg.content}")

    print("\n" + "=" * 70)
    print("  Demo completada. DuckDB + LangGraph integrados exitosamente.")
    print("=" * 70)

    conn.close()


if __name__ == "__main__":
    run_duckdb_langgraph_demo()
