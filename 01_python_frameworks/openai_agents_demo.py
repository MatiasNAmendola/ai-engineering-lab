# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai-agents>=0.0.1",
# ]
# ///
"""
openai_agents_demo.py

Demostración del SDK de OpenAI Agents para Ingeniería de IA:
1. Creación de Agentes con herramientas (tools) personalizadas.
2. Decorador @function_tool para definir herramientas tipadas.
3. Handoffs: delegación de tareas entre agentes especializados.
4. Ejecución síncrona (Runner.run_sync) y asíncrona (Runner.run).

Ejecución: uv run 01_python_frameworks/openai_agents_demo.py
"""

import os
import asyncio
from agents import Agent, Runner, function_tool


# ==========================================
# 1. HERRAMIENTAS CON @function_tool
# ==========================================

def _query_pgvector(table: str, top_k: int = 5) -> str:
    """Ejecuta una búsqueda de similitud vectorial sobre una tabla de pgvector en PostgreSQL."""
    print(f"   [Tool: query_pgvector] Buscando top {top_k} en tabla '{table}'...")
    return (
        f"Resultados de '{table}' (top {top_k}):\n"
        f"  1. doc_id=101 | similitud=0.95 | 'PostgreSQL con pgvector unifica búsqueda vectorial y SQL.'\n"
        f"  2. doc_id=207 | similitud=0.89 | 'Los índices HNSW aceleran consultas ANN en millones de filas.'\n"
        f"  3. doc_id=042 | similitud=0.82 | 'Embeddings de OpenAI text-embedding-3-small: 1536 dimensiones.'"
    )

def _check_db_health(host: str = "127.0.0.1", port: int = 5432) -> str:
    """Verifica el estado de conexión de una instancia de PostgreSQL."""
    print(f"   [Tool: check_db_health] Verificando {host}:{port}...")
    return f"PostgreSQL en {host}:{port} -> status=healthy, latency=2ms, connections_active=12."

def _estimate_index_size(num_vectors: int, dimensions: int = 1536) -> str:
    """Estima el tamaño en disco de un índice HNSW para pgvector."""
    bytes_per_dim = 4
    overhead_factor = 1.3
    size_bytes = num_vectors * dimensions * bytes_per_dim * overhead_factor
    size_gb = size_bytes / (1024 ** 3)
    print(f"   [Tool: estimate_index_size] Calculando para {num_vectors} vectores de {dimensions}d...")
    return f"Índice HNSW estimado: {size_gb:.2f} GB para {num_vectors:,} vectores de {dimensions} dimensiones."

query_pgvector = function_tool(_query_pgvector, name_override="query_pgvector")
check_db_health = function_tool(_check_db_health, name_override="check_db_health")
estimate_index_size = function_tool(_estimate_index_size, name_override="estimate_index_size")


# ==========================================
# 2. DEFINICIÓN DE AGENTES
# ==========================================

# Agente especialista en búsqueda vectorial
vector_search_agent = Agent(
    name="Vector Search Specialist",
    instructions=(
        "Eres un especialista en búsqueda vectorial con pgvector y PostgreSQL. "
        "Respondes consultas sobre embeddings, índices HNSW/IVFFlat y similitud semántica. "
        "Usa las herramientas disponibles para obtener datos concretos."
    ),
    tools=[query_pgvector, estimate_index_size],
)

# Agente especialista en infraestructura y operaciones
db_ops_agent = Agent(
    name="DB Ops Engineer",
    instructions=(
        "Eres un ingeniero de operaciones de bases de datos PostgreSQL. "
        "Monitoreas salud de instancias, rendimiento y configuración. "
        "Usa las herramientas para verificar el estado del sistema."
    ),
    tools=[check_db_health, estimate_index_size],
)

# Agente orquestador que delega (handoff) a los especialistas
orchestrator_agent = Agent(
    name="AI Platform Orchestrator",
    instructions=(
        "Eres el orquestador principal de una plataforma de IA. "
        "Recibes consultas del usuario y las delegas al agente especialista apropiado. "
        "Si la consulta es sobre búsqueda vectorial o embeddings, delega al Vector Search Specialist. "
        "Si la consulta es sobre salud, rendimiento o infraestructura, delega al DB Ops Engineer. "
        "Siempre explica brevemente por qué delegas la tarea."
    ),
    handoffs=[vector_search_agent, db_ops_agent],
)


# ==========================================
# 3. MODO MOCK (SIN API KEY)
# ==========================================

def run_mock_demo():
    """Simula el flujo completo del SDK sin realizar llamadas a la API de OpenAI."""
    print("[NOTE] No se encontró OPENAI_API_KEY. Ejecutando demostración en modo simulado.\n")

    print("--- Paso 1: Herramientas con @function_tool ---")
    print("Las herramientas se definen como funciones Python decoradas con @function_tool.")
    print("El SDK genera automáticamente el schema JSON para el LLM.\n")

    print("Invocando _query_pgvector('productos', top_k=3):")
    result = _query_pgvector("productos", top_k=3)
    print(f"  Respuesta:\n{result}\n")

    print("Invocando _check_db_health('10.0.0.5', 5432):")
    result = _check_db_health("10.0.0.5", 5432)
    print(f"  Respuesta: {result}\n")

    print("Invocando _estimate_index_size(10_000_000, 1536):")
    result = _estimate_index_size(10_000_000, 1536)
    print(f"  Respuesta: {result}\n")

    print("--- Paso 2: Agentes Especializados ---")
    print(f"  Agente: '{vector_search_agent.name}'")
    print(f"    Tools: {[t.name for t in vector_search_agent.tools]}")
    print(f"  Agente: '{db_ops_agent.name}'")
    print(f"    Tools: {[t.name for t in db_ops_agent.tools]}\n")

    print("--- Paso 3: Handoff entre Agentes (Simulado) ---")
    print(f"  Orquestador: '{orchestrator_agent.name}'")
    print(f"    Handoffs disponibles: {[h.name if hasattr(h, 'name') else h for h in orchestrator_agent.handoffs]}\n")

    print("  [Simulación] Usuario: '¿Cuánto espacio necesita un índice HNSW para 5M de embeddings?'")
    print("  [Orquestador] Esta consulta es sobre dimensionamiento de índices -> delego al Vector Search Specialist.")
    print("  [Vector Search Specialist] Invoco estimate_index_size(5_000_000, 1536)...")
    result = _estimate_index_size(5_000_000, 1536)
    print(f"  [Respuesta Final] {result}\n")

    print("  [Simulación] Usuario: '¿Está saludable el servidor de base de datos?'")
    print("  [Orquestador] Esta consulta es sobre infraestructura -> delego al DB Ops Engineer.")
    print("  [DB Ops Engineer] Invoco check_db_health()...")
    result = _check_db_health()
    print(f"  [Respuesta Final] {result}\n")

    print("--- Paso 4: Ejecución Síncrona vs Asíncrona ---")
    print("  Runner.run_sync(agent, prompt)  -> Ejecución bloqueante, ideal para scripts.")
    print("  await Runner.run(agent, prompt) -> Ejecución async, ideal para servidores y APIs.")
    print("  El SDK maneja automáticamente el ciclo: LLM -> tool_call -> LLM -> respuesta.\n")


# ==========================================
# 4. MODO REAL (CON API KEY)
# ==========================================

async def run_real_demo():
    """Ejecuta el flujo real contra la API de OpenAI."""
    print("=== Demo de OpenAI Agents SDK (Modo Real) ===\n")

    print("--- Paso 1: Agente con herramientas ---")
    prompt = "Buscá los 3 documentos más similares en la tabla 'articulos_tecnicos' y decime qué encontraste."
    print(f"Pregunta: '{prompt}'")
    result = await Runner.run(vector_search_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")

    print("--- Paso 2: Handoff entre agentes ---")
    prompt = "Necesito saber si el servidor PostgreSQL está saludable y luego estimar el índice para 2 millones de vectores."
    print(f"Pregunta: '{prompt}'")
    result = await Runner.run(orchestrator_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")

    print("--- Paso 3: Ejecución síncrona ---")
    prompt = "¿Cuánto espacio en disco ocupa un índice HNSW para 1 millón de embeddings de 1536 dimensiones?"
    print(f"Pregunta: '{prompt}'")
    result = Runner.run_sync(vector_search_agent, prompt)
    print(f"Respuesta: {result.final_output}\n")


# ==========================================
# ENTRY POINT
# ==========================================

def run_demo():
    print("==========================================================")
    print("  OpenAI Agents SDK - Demo para Ingeniería de IA")
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
