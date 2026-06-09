# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "crewai>=0.1.0",
# ]
# ///
"""
crewai_demo.py

Demostración de CrewAI: framework multi-agente basado en roles y tareas.
Se simula un equipo de dos agentes (Arquitecto de BD + Auditor de Seguridad)
que colaboran secuencialmente para evaluar un stack de datos con pgvector.

Ejecución: uv run 01_python_frameworks/crewai_demo.py
"""

import os
import sys

try:
    from crewai import Agent, Task, Crew, Process
    CREWAI_AVAILABLE = True
except Exception:
    CREWAI_AVAILABLE = False


# ==========================================
# MODO MOCK (sin API Key o sin crewai disponible)
# ==========================================

MOCK_ARCHITECT_OUTPUT = (
    "Tras evaluar la propuesta de PostgreSQL + pgvector para 50 millones de documentos, "
    "la recomendación es **adaptar** la solución. pgvector con índices HNSW ofrece un rendimiento "
    "aceptable hasta ~20 millones de vectores de 768 dimensiones en hardware estándar. Más allá de "
    "ese umbral, la latencia de búsqueda ANN se degrada y el costo de mantenimiento de índices crece.\n\n"
    "Para escalar, se recomienda particionar la tabla vectorial por dominio semántico y usar "
    "pgvector como capa de ingestión y consulta primaria, con una base vectorial dedicada (Qdrant o "
    "Weaviate) como caché de búsqueda para consultas de alta concurrencia.\n\n"
    "En resumen: pgvector es viable como motor único hasta 20M de documentos. Para 50M, adoptar un "
    "modelo híbrido con PostgreSQL como source of truth y un motor vectorial externo para serving."
)

MOCK_SECURITY_OUTPUT = (
    "Se identifican tres riesgos críticos en el stack propuesto:\n"
    "1) **Exposición de embeddings en logs**: Los vectores almacenados pueden reconstruir información "
    "sensible del texto original. Se debe prohibir el logueo de columnas vectoriales en logs de "
    "aplicación y auditoría.\n"
    "2) **Falta de Row-Level Security (RLS)**: Las tablas con embeddings deben tener políticas RLS "
    "activas para evitar que usuarios no autorizados consulten vectores de documentos restringidos.\n"
    "3) **Gobernanza de datos embebidos**: Si los documentos fuente contienen PII, los embeddings "
    "heredan ese riesgo. Se requiere un pipeline de anonimización previo a la vectorización.\n\n"
    "Mitigaciones: Activar RLS en todas las tablas vectoriales, implementar masking de columnas "
    "embedding en logs, y establecer un gate de gobernanza pre-vectorización con detección de PII."
)


def run_mock_demo(reason: str):
    print(f"\n[NOTE] {reason}. Usando respuestas simuladas.\n")

    print("=" * 60)
    print("  CREWAI DEMO — Equipo de Evaluación de Stack de Datos")
    print("=" * 60)

    print("\n--- Paso 1: Arquitecto de BD analiza la propuesta ---")
    print(f"\n{MOCK_ARCHITECT_OUTPUT}")

    print("\n--- Paso 2: Auditor de Seguridad revisa y añade dictamen ---")
    print(f"\n{MOCK_SECURITY_OUTPUT}")

    print("\n" + "=" * 60)
    print("  Resultado Final del Crew (Secuencial)")
    print("=" * 60)
    print(f"\n{MOCK_SECURITY_OUTPUT}")


# ==========================================
# MODO EN VIVO (con CrewAI + API Key)
# ==========================================

def run_live_demo():
    api_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = api_key

    db_architect = Agent(
        role="Arquitecto de Bases de Datos Senior",
        goal="Diseñar stacks de datos robustos y escalables para cargas de trabajo de IA.",
        backstory=(
            "Eres un arquitecto de bases de datos con más de 15 años de experiencia en sistemas "
            "transaccionales y vectoriales. Tu especialidad es PostgreSQL con pgvector y sabes "
            "cuándo un motor relacional es suficiente versus cuando se necesita una base vectorial dedicada."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gemini/gemini-1.5-flash",
    )

    security_auditor = Agent(
        role="Auditor de Seguridad y Gobernanza de Datos",
        goal="Garantizar que los stacks de datos cumplan con políticas de seguridad, privacidad y gobernanza.",
        backstory=(
            "Eres un auditor de seguridad enfocado en gobernanza de datos corporativa. "
            "Evalúas riesgos de exposición de embeddings, control de acceso a nivel de fila (RLS), "
            "y cumplimiento de normativas como GDPR y SOC2 en infraestructuras de IA."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gemini/gemini-1.5-flash",
    )

    task_architecture = Task(
        description=(
            "Evalúa la propuesta de usar PostgreSQL + pgvector como motor único para un sistema "
            "de búsqueda semántica sobre 50 millones de documentos. Analiza ventajas, limitaciones "
            "de rendimiento en índices HNSW, y alternativas si el volumen crece."
        ),
        expected_output=(
            "Un informe técnico de 3 párrafos con recomendación final: adoptar, adaptar o descartar pgvector."
        ),
        agent=db_architect,
    )

    task_security = Task(
        description=(
            "Revisa la evaluación del Arquitecto de BD y añade un análisis de riesgos de seguridad: "
            "exposición de embeddings en logs, necesidad de Row-Level Security en tablas vectoriales, "
            "y controles de gobernanza para datos sensibles embebidos en los vectores."
        ),
        expected_output=(
            "Un dictamen de seguridad de 2 párrafos con riesgos identificados y mitigaciones recomendadas."
        ),
        agent=security_auditor,
    )

    crew = Crew(
        agents=[db_architect, security_auditor],
        tasks=[task_architecture, task_security],
        process=Process.sequential,
        verbose=True,
    )

    print("=" * 60)
    print("  CREWAI DEMO — Equipo de Evaluación de Stack de Datos")
    print("  (Modo en vivo con Gemini 1.5 Flash)")
    print("=" * 60)
    print("\nEjecutando crew.kickoff()...")

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("  Resultado Final del Crew")
    print("=" * 60)
    print(f"\n{result}")


if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")

    if not CREWAI_AVAILABLE:
        run_mock_demo("crewai no pudo importarse (incompatibilidad de dependencias con esta versión de Python)")
    elif not api_key:
        run_mock_demo("No se encontró GEMINI_API_KEY")
    else:
        run_live_demo()
