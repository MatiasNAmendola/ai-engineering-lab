# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "deepagents>=0.6.0",
# ]
# ///
"""
deepagents_demo.py

Demostración de LangChain DeepAgents: framework para construir agentes autónomos
con sub-agentes especializados, herramientas customizadas y streaming de eventos.

Conceptos clave:
1. create_deep_agent(): Fábrica única que retorna un CompiledStateGraph (LangGraph).
2. Model-agnostic: formato "provider:model" para cualquier proveedor de LLM.
3. Sub-agentes: agentes delegados con ventanas de contexto aisladas.
4. Middleware integrado: TodoList, Skills, Filesystem, SubAgent, Summarization.
5. Streaming: eventos en tiempo real con agent.stream_events().

Ejecución: uv run 01_python_frameworks/deepagents_demo.py
"""

import os
import json
from typing import Any


# ==========================================
# HERRAMIENTAS CUSTOMIZADAS
# ==========================================

def analyze_schema(table_name: str) -> str:
    """Analiza el esquema de una tabla y retorna métricas de gobernanza."""
    print(f"   [Tool: analyze_schema] Inspeccionando tabla: '{table_name}'")
    schemas = {
        "products": {
            "columns": 14,
            "indexes": 3,
            "has_pii": False,
            "vector_columns": ["embedding_768"],
            "row_estimate": "10.2M",
            "governance_score": 0.92,
        },
        "users": {
            "columns": 9,
            "indexes": 2,
            "has_pii": True,
            "vector_columns": [],
            "row_estimate": "2.8M",
            "governance_score": 0.78,
        },
    }
    result = schemas.get(table_name, {"error": f"Tabla '{table_name}' no encontrada"})
    return json.dumps(result, indent=2)


def vector_search(query: str, top_k: int = 3) -> str:
    """Ejecuta una búsqueda vectorial semántica en pgvector."""
    print(f"   [Tool: vector_search] Buscando: '{query}' (top_k={top_k})")
    results = [
        {"id": 1, "score": 0.94, "text": "Índice HNSW recomendado para embeddings de 768 dims"},
        {"id": 2, "score": 0.87, "text": "pgvector soporta distancia coseno y L2"},
        {"id": 3, "score": 0.81, "text": "Particionar por tenant mejora recall en multi-tenant"},
    ]
    return json.dumps(results[:top_k], indent=2)


# ==========================================
# MODO MOCK (sin API Key)
# ==========================================

def run_mock_demo():
    """Simula el flujo completo de DeepAgents sin conexión a LLM."""
    print("\n[NOTE] No se encontró GEMINI_API_KEY. Usando modo simulado.\n")

    print("--- Paso 1: Creando Deep Agent ---")
    print("   create_deep_agent(")
    print('     model="google_genai:gemini-1.5-flash",')
    print("     tools=[analyze_schema, vector_search],")
    print('     system_prompt="Eres un ingeniero de datos especializado en gobernanza.",')
    print("     subagents=[research_agent],")
    print("   )")
    print("   -> CompiledStateGraph listo.\n")

    print("--- Paso 2: Invocando agente con streaming ---")
    print('   Input: "Analiza el esquema de products y busca mejores prácticas de indexación vectorial"\n')

    print("   [Stream Event] on_chat_model_start")
    print("   [Stream Event] on_tool_start -> analyze_schema('products')")

    schema_result = analyze_schema("products")
    print(f"   [Tool Result] {schema_result}\n")

    print("   [Stream Event] on_tool_start -> vector_search('mejores prácticas indexación vectorial')")

    search_result = vector_search("mejores prácticas indexación vectorial")
    print(f"   [Tool Result] {search_result}\n")

    print("   [Stream Event] on_chat_model_stream (delegando a sub-agente research-agent)")
    print("   [Sub-Agent: research-agent] Analizando resultados de búsqueda vectorial...")
    print("   [Sub-Agent: research-agent] Contexto aislado: 2 tool results, 1 schema analysis\n")

    print("   [Stream Event] on_chat_model_end")
    print("   [Stream Event] on_chain_end\n")

    print("--- Paso 3: Resultado Final ---")
    print("   Respuesta del agente:")
    print("   'El esquema de products tiene 14 columnas con score de gobernanza 0.92.")
    print("    Incluye columna vectorial embedding_768. Recomendaciones:")
    print("    1. Usar índice HNSW para embeddings de 768 dimensiones.")
    print("    2. pgvector soporta distancia coseno y L2 nativamente.")
    print("    3. Considerar particionamiento por tenant para mejorar recall.'\n")

    print("--- Paso 4: Resumen de Middleware Activo ---")
    print("   [TodoList] 2 tareas completadas: schema analysis, vector search")
    print("   [SubAgent] 1 delegación a research-agent")
    print("   [Summarization] Contexto comprimido: 3 mensajes -> 1 resumen\n")


# ==========================================
# MODO REAL (con API Key)
# ==========================================

def run_live_demo():
    """Ejecuta el agente DeepAgents con conexión real a Gemini."""
    from deepagents import create_deep_agent

    print("\n--- Paso 1: Creando Deep Agent con Gemini ---")

    agent = create_deep_agent(
        model="google_genai:gemini-1.5-flash",
        tools=[analyze_schema, vector_search],
        system_prompt=(
            "Eres un ingeniero de datos senior especializado en gobernanza de bases de datos "
            "y búsqueda vectorial. Analizas esquemas, recomiendas índices y aseguras "
            "cumplimiento de PII. Responde siempre en español."
        ),
        subagents=[
            {
                "name": "research-agent",
                "description": "Delega tareas de investigación sobre mejores prácticas de indexación vectorial.",
                "system_prompt": (
                    "Eres un investigador especializado en bases de datos vectoriales y pgvector. "
                    "Proporciona recomendaciones técnicas precisas."
                ),
            },
        ],
    )

    print("   -> CompiledStateGraph creado exitosamente.\n")

    print("--- Paso 2: Invocando agente con streaming ---")
    user_query = "Analiza el esquema de products y busca mejores prácticas de indexación vectorial"
    print(f'   Input: "{user_query}"\n')

    print("--- Paso 3: Stream de Eventos ---")

    input_messages = {"messages": [{"role": "user", "content": user_query}]}

    final_response = ""
    for event in agent.stream_events(input_messages, version="v2"):
        kind = event["event"]

        if kind == "on_tool_start":
            tool_name = event["name"]
            print(f"   [Stream] on_tool_start -> {tool_name}")

        elif kind == "on_tool_end":
            output = event["data"].get("output", "")
            preview = str(output)[:120]
            print(f"   [Stream] on_tool_end -> {preview}...")

        elif kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                final_response += chunk.content

        elif kind == "on_chat_model_end":
            print("   [Stream] on_chat_model_end")

    print(f"\n--- Paso 4: Resultado Final ---")
    print(f"   {final_response}\n")


# ==========================================
# EJECUCIÓN PRINCIPAL
# ==========================================

def main():
    print("==========================================================")
    print("  DeepAgents Demo — LangChain DeepAgents para IA Engineering Lab")
    print("==========================================================")

    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        print("\n  Modo: LIVE (Gemini API conectada)")
        run_live_demo()
    else:
        print("\n  Modo: MOCK (sin API key)")
        run_mock_demo()

    print("==========================================================")


if __name__ == "__main__":
    main()
