# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic-ai>=0.0.1",
#     "pydantic>=2.0.0",
#     "logfire>=0.1.0",
# ]
# ///
"""
pydantic_ai_demo.py

Ejemplo de Agente de PydanticAI enfocado en validación estructural y tipado estricto.
Se autogestiona con uv utilizando metadatos PEP 723 en línea.
Ejecución: uv run pydantic_ai_demo.py
"""

import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

# 1. Definición del Esquema de Salida mediante Pydantic
class DatabaseConfig(BaseModel):
    engine: str = Field(description="Motor de base de datos a utilizar, e.g., PostgreSQL, Qdrant, Badger.")
    is_vector_db: bool = Field(description="Booleano que indica si el motor tiene indexación y búsqueda vectorial.")
    estimated_volume_millions: float = Field(description="Volumen estimado de registros en millones.")

class AIArchitectureProfile(BaseModel):
    architecture_style: str = Field(description="Estilo general de la arquitectura, e.g., Relacional, Serverless, LSM-Tree.")
    primary_database: DatabaseConfig = Field(description="Configuración detallada de la base de datos principal recomendada.")
    justification: str = Field(description="Justificación técnica de por qué se seleccionó este diseño y stack.")

# 2. Configuración del Agente de PydanticAI
# Declaramos que el agente retornará obligatoriamente una instancia de AIArchitectureProfile
api_key = os.environ.get("GEMINI_API_KEY")

if api_key:
    # Usamos el modelo real configurado
    # PydanticAI soporta gemini-1.5-flash y asocia la API_KEY del entorno
    agent = Agent(
        'google-gla:gemini-1.5-flash',
        output_type=AIArchitectureProfile,
        system_prompt=(
            "Eres un arquitecto técnico principal y CTO. Evalúa los requerimientos de la "
            "organización y recomienda un stack de datos pragmático enfocado en IA."
        )
    )
else:
    print("\n[NOTE] No se encontró GEMINI_API_KEY. Usando el TestModel fuera de línea de PydanticAI.")
    # El TestModel de PydanticAI genera automáticamente respuestas que coinciden con el esquema
    # También podemos pasar una función customizada o una instancia del modelo para simular respuestas:
    agent = Agent(
        TestModel(
            custom_output_args=AIArchitectureProfile(
                architecture_style="Relacional Pragmático (Postgres + pgvector)",
                primary_database=DatabaseConfig(
                    engine="PostgreSQL",
                    is_vector_db=True,
                    estimated_volume_millions=10.0
                ),
                justification=(
                    "Se recomienda PostgreSQL con la extensión pgvector porque unifica la "
                    "consistencia transaccional relacional con la indexación de embeddings en un "
                    "solo motor, evitando la complejidad operativa de sincronización de bases de datos dedicadas."
                )
            )
        ),
        output_type=AIArchitectureProfile
    )

def run_demo():
    print("=== Demo de PydanticAI (Ejecutado con uv) ===")
    
    prompt = (
        "Hola, soy CTO en una empresa de e-commerce. Queremos inyectar embeddings semánticos "
        "en nuestro motor de búsqueda relacional para 10 millones de productos de forma segura. "
        "¿Qué base de datos nos recomiendas?"
    )
    
    print(f"Pregunta del Usuario:\n'{prompt}'\n")
    print("Procesando consulta y validando estructura...")
    
    # Ejecuta el agente (invoca e instancia el esquema de forma síncrona)
    result = agent.run_sync(prompt)
    
    # El objeto retornado en result.output es de tipo AIArchitectureProfile (garantizado por PydanticAI)
    profile: AIArchitectureProfile = result.output
    
    print("\nPerfil de Arquitectura Extrapolado de Forma Segura:")
    print(f"  Estilo de Arquitectura: {profile.architecture_style}")
    print(f"  Base de Datos:          {profile.primary_database.engine}")
    print(f"  Es Vectorial:           {profile.primary_database.is_vector_db}")
    print(f"  Volumen Estimado:       {profile.primary_database.estimated_volume_millions} Millones")
    print(f"  Justificación:          {profile.justification}")

if __name__ == "__main__":
    run_demo()
