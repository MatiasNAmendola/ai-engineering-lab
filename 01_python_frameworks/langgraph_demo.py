# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "langgraph>=0.1.0",
#     "langchain>=0.2.0",
#     "langchain-google-genai>=1.0.0",
#     "langsmith>=0.1.0",
#     "langfuse>=2.0.0",
#     "langserve>=0.2.0",
#     "fastapi>=0.100.0",
#     "uvicorn>=0.22.0",
#     "langmem>=0.0.1",
# ]
# ///
"""
langgraph_demo.py

Demostración completa y explicativa de toda la suite de herramientas "lang..." para Ingeniería de IA:
1. LangChain: Estructura de mensajes, prompts y wrappers de modelos.
2. LangGraph: Bucles de decisión ReAct, estado de agente y persistencia de memoria de corto plazo.
3. LangSmith: Trazas corporativas y depuración nativa en la nube.
4. LangFuse: Telemetría de código abierto, costo de tokens y auditoría de prompts.
5. LangServe: Exposición de agentes como APIs web FastAPI auto-documentadas.
6. LangMem: Motor de memoria episódica y semántica a largo plazo.

Ejecución estándar: uv run 01_python_frameworks/langgraph_demo.py
Ejecutar servidor LangServe: uv run 01_python_frameworks/langgraph_demo.py --serve
"""

import os
import sys
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# 1. LangSmith (Trazabilidad nativa)
from langsmith import Client as LangSmithClient

# 2. LangFuse (Telemetría y evaluación de código abierto)
from langfuse import Langfuse

# 3. LangMem (Memoria semántica y a largo plazo del usuario)
# Nota: LangMem extiende el grafo de agentes para aprender y retener conocimientos entre sesiones

# 4. LangServe (Servicios REST y API auto-documentados)
from fastapi import FastAPI
import uvicorn
from langserve import add_routes


# ==========================================
# DEFINICIÓN DE COMPONENTES DEL AGENTE
# ==========================================

# Definimos el Estado del Agente (LangGraph gestiona y persiste este diccionario estructurado)
class AgentState(TypedDict):
    # add_messages concatena las respuestas de forma segura al historial
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Memoria de largo plazo simulada/persistida (LangMem)
    user_preferences: dict

# Herramienta para simular lectura de base de datos
def database_checker_tool(query: str) -> str:
    """Inspecciona el estado de conexión de PostgreSQL + pgvector."""
    print(f"   [Tool: database_checker_tool] Procesando: '{query}'")
    return "Resultado: Conexión producción activa en host=127.0.0.1; port=5432; status=healthy."

# Nodo del Agente (LangChain + LangGraph)
def call_model(state: AgentState):
    """Nodo del LLM que decide el razonamiento."""
    messages = state["messages"]
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # Si tenemos preferencias de largo plazo aprendidas, las inyectamos en el contexto
    pref_text = ""
    if state.get("user_preferences"):
        pref_text = f"\n[Preferencias de largo plazo aprendidas (LangMem)]: {state['user_preferences']}"
    
    if api_key:
        # LangChain unifica la llamada al modelo Gemini
        model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        # Inyectamos contexto
        if pref_text:
            messages = [HumanMessage(content=messages[0].content + pref_text)] + list(messages[1:])
        response = model.invoke(messages)
        return {"messages": [response]}
    else:
        # Modo de simulación (Mock) sin API Key
        last_message = messages[-1].content
        print("\n[NOTE] No se encontró GEMINI_API_KEY. Usando respuesta simulada de LangChain.")
        
        if len(messages) == 1 and ("verificar" in last_message.lower() or "status" in last_message.lower()):
            mock_ai_message = AIMessage(
                content=f"Decido buscar el estado del sistema en la base de datos.{pref_text}",
                additional_kwargs={"tool_calls": [{"name": "database_checker_tool", "args": "verify_status"}]}
            )
        else:
            mock_ai_message = AIMessage(
                content=f"El estado del sistema es correcto y saludable. Prefs recordadas: {state.get('user_preferences')}"
            )
        return {"messages": [mock_ai_message]}

# Nodo de Herramientas
def call_tool(state: AgentState):
    """Nodo que ejecuta la herramienta."""
    tool_result = database_checker_tool("verify_status")
    return {"messages": [HumanMessage(content=tool_result)]}

# Enrutador ReAct condicional
def should_continue(state: AgentState):
    """Decide si el bucle ReAct continúa o termina."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "additional_kwargs") and "tool_calls" in last_message.additional_kwargs:
        return "continue"
    return "end"

# Construcción y compilación del Grafo
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", call_tool)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END
    }
)
workflow.add_edge("tools", "agent")

# LangGraph Checkpointer para persistencia local de corto plazo en memoria
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)


# ==========================================
# DEMOSTRACIÓN DE PROPÓSITOS DE LA SUITE
# ==========================================

def run_suite_demo():
    print("==========================================================")
    # 1. LANGCHAIN
    print("🟢 1. LANGCHAIN (Librería de Orquestación)")
    print("   - Propósito: Unifica llamadas a LLMs y estructuras de mensajes.")
    print("   - Demostración: Representación de mensajes HumanMessage y AIMessage.")
    
    # 2. LANGGRAPH
    print("\n🟢 2. LANGGRAPH (Agentes con Estado y Bucles)")
    print("   - Propósito: Permite ciclos ReAct y persistencia de corto plazo.")
    print("   - Demostración: Corriendo agente con checkpoint de memoria de sesión (Thread ID: 42).")
    
    config = {"configurable": {"thread_id": "42"}}
    inputs = {"messages": [HumanMessage(content="Por favor verifica el status del servidor de base de datos.")]}
    
    print("\n--- Ejecución del Grafo ---")
    for output in app.stream(inputs, config=config):
        for key, value in output.items():
            print(f"[Nodo: {key}]")
            for msg in value.get("messages", []):
                print(f"  Role: {type(msg).__name__} | Contenido: {msg.content}")

    # 3. LANGSMITH
    print("\n🟢 3. LANGSMITH (Trazabilidad y Depuración Corporativa)")
    print("   - Propósito: Registra cada paso de ejecución del modelo y herramientas automáticamente en la nube de LangChain.")
    print("   - Activación: Se habilita inyectando variables de entorno:")
    print("     export LANGCHAIN_TRACING_V2='true'")
    print("     export LANGCHAIN_API_KEY='lsv2_...'")
    
    # Verificación local
    LangSmithClient()
    print(f"   - Estado: Client inicializado. Tracing habilitado en entorno = {os.environ.get('LANGCHAIN_TRACING_V2', 'false')}")

    # 4. LANGFUSE
    print("\n🟢 4. LANGFUSE (Telemetría de Código Abierto)")
    print("   - Propósito: Alternativa self-hosted para monitorizar costos, latencias y auditoría de prompts.")
    print("   - Integración: CallbackHandler inyectado en llamadas de LangChain.")
    
    Langfuse()
    print("   - Estado: SDK de Langfuse importado. Integración callback lista para registrar trazas.")

    # 5. LANGMEM
    print("\n🟢 5. LANGMEM (Memoria Semántica de Largo Plazo)")
    print("   - Propósito: Persiste conocimientos y preferencias del usuario entre múltiples hilos y sesiones.")
    print("   - Demostración: Simulamos la persistencia de una preferencia del usuario:")
    
    # Simulamos el comportamiento de LangMem: recordar que el usuario prefiere "PostgreSQL"
    print("   - Guardando en LangMem: {'preferencias': 'Usa Postgres para índices vectoriales'}")
    memoria_largo_plazo = {"motor_preferido": "PostgreSQL (pgvector)"}
    
    # Ejecutamos una segunda sesión (Thread 43) inyectando la memoria de largo plazo recuperada
    print("\n--- Corriendo segunda sesión con memoria a largo plazo (LangMem) ---")
    config_session_2 = {"configurable": {"thread_id": "43"}}
    inputs_session_2 = {
        "messages": [HumanMessage(content="¿Cuál es mi motor de base de datos preferido?")],
        "user_preferences": memoria_largo_plazo
    }
    
    for output in app.stream(inputs_session_2, config=config_session_2):
        for key, value in output.items():
            print(f"[Nodo: {key}]")
            for msg in value.get("messages", []):
                print(f"  Role: {type(msg).__name__} | Contenido: {msg.content}")

    # 6. LANGSERVE
    print("\n🟢 6. LANGSERVE (Despliegue y Exposición de APIs)")
    print("   - Propósito: Convierte grafos de LangGraph en endpoints REST de producción con Swagger.")
    print("   - Comando: Para levantar el servidor local interactivo de Swagger y consumir el agente por HTTP, ejecuta:")
    print("     uv run 01_python_frameworks/langgraph_demo.py --serve")
    print("==========================================================")


# ==========================================
# CONFIGURACIÓN DEL SERVIDOR LANGSERVE
# ==========================================

def run_server():
    print("\n🚀 Iniciando Servidor LangServe en http://localhost:8000 ...")
    print("📖 Documentación Swagger interactiva en http://localhost:8000/docs")
    print("🎯 Endpoint del Agente expuesto en: http://localhost:8000/agent/invoke")
    
    # Inicializamos FastAPI
    app_fastapi = FastAPI(
        title="AI Engineering Lab Agent Server",
        version="1.0.0",
        description="Servidor LangServe que expone el agente LangGraph mediante endpoints REST."
    )
    
    # Registramos las rutas del agente compilado usando LangServe
    add_routes(
        app_fastapi,
        app,
        path="/agent",
    )
    
    # Corremos uvicorn
    uvicorn.run(app_fastapi, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    # Si se pasa el flag --serve, levantamos LangServe
    if "--serve" in sys.argv:
        run_server()
    else:
        run_suite_demo()
