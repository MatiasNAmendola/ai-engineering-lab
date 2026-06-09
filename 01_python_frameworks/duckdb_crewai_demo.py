# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.0.0",
#     "crewai>=1.14.6",
# ]
# ///
"""
duckdb_crewai_demo.py

Integración de DuckDB (base de datos analítica en proceso) con CrewAI (framework multi-agente).
Se crea un equipo de tres agentes de IA que consultan datos REALES en DuckDB para analizar
métricas de operaciones de ingeniería de IA: costos de embeddings, uso de APIs, calidad de datos.

DuckDB provee la capa de datos analítica real (sin mocks, sin archivos externos).
CrewAI orquesta agentes con roles especializados que ejecutan queries SQL reales.

Ejecución: uv run 01_python_frameworks/duckdb_crewai_demo.py
"""

import os
import sys

import duckdb

try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except Exception:
    CREWAI_AVAILABLE = False


# ==========================================
# CAPA DE DATOS: DuckDB en memoria con datos reales
# ==========================================

def crear_base_de_datos() -> duckdb.DuckDBPyConnection:
    """Crea una base DuckDB en memoria con métricas realistas de operaciones de IA."""
    conn = duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE embedding_jobs (
            job_id INTEGER PRIMARY KEY,
            mes TEXT NOT NULL,
            modelo TEXT NOT NULL,
            documentos_procesados INTEGER NOT NULL,
            tokens_totales BIGINT NOT NULL,
            costo_usd DECIMAL(10, 4) NOT NULL,
            latencia_promedio_ms INTEGER NOT NULL,
            calidad_score DECIMAL(3, 2) NOT NULL,
            categoria TEXT NOT NULL
        )
    """)

    conn.execute("""
        INSERT INTO embedding_jobs VALUES
            (1,  '2025-01', 'text-embedding-3-small',  1200,   4800000,   0.9600,  120, 0.92, 'documentos'),
            (2,  '2025-01', 'text-embedding-3-large',   300,   1500000,   1.9500,  340, 0.97, 'documentos'),
            (3,  '2025-01', 'text-embedding-3-small',   800,   3200000,   0.6400,  115, 0.88, 'chunks'),
            (4,  '2025-02', 'text-embedding-3-small',  1500,   6000000,   1.2000,  125, 0.91, 'documentos'),
            (5,  '2025-02', 'text-embedding-3-large',   450,   2250000,   2.9250,  350, 0.96, 'documentos'),
            (6,  '2025-02', 'text-embedding-3-small',  1100,   4400000,   0.8800,  118, 0.85, 'chunks'),
            (7,  '2025-03', 'text-embedding-3-small',  2000,   8000000,   1.6000,  130, 0.93, 'documentos'),
            (8,  '2025-03', 'text-embedding-3-large',   600,   3000000,   3.9000,  360, 0.98, 'documentos'),
            (9,  '2025-03', 'text-embedding-3-small',  1400,   5600000,   1.1200,  122, 0.90, 'chunks'),
            (10, '2025-03', 'text-embedding-ada-002',    50,    200000,   0.0200,   95, 0.75, 'metadata'),
            (11, '2025-04', 'text-embedding-3-small',  2200,   8800000,   1.7600,  128, 0.94, 'documentos'),
            (12, '2025-04', 'text-embedding-3-large',   700,   3500000,   4.5500,  355, 0.97, 'documentos'),
            (13, '2025-04', 'text-embedding-3-small',  1600,   6400000,   1.2800,  120, 0.89, 'chunks'),
            (14, '2025-04', 'text-embedding-ada-002',    80,    320000,   0.0320,   90, 0.72, 'metadata')
    """)

    conn.execute("""
        CREATE TABLE api_calls (
            call_id INTEGER PRIMARY KEY,
            mes TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            tokens_input BIGINT NOT NULL,
            tokens_output BIGINT NOT NULL,
            costo_usd DECIMAL(10, 4) NOT NULL,
            latencia_ms INTEGER NOT NULL,
            status_code INTEGER NOT NULL
        )
    """)

    conn.execute("""
        INSERT INTO api_calls VALUES
            (1,  '2025-01', '/v1/chat/completions',  'openai',    50000,   12000,  0.3800,   800, 200),
            (2,  '2025-01', '/v1/chat/completions',  'openai',    80000,   25000,  0.6500,  1200, 200),
            (3,  '2025-01', '/v1/embeddings',        'openai',   200000,       0,  0.2000,   450, 200),
            (4,  '2025-01', '/v1/chat/completions',  'anthropic', 60000,   18000,  0.7200,   950, 200),
            (5,  '2025-02', '/v1/chat/completions',  'openai',    95000,   30000,  0.7750,  1100, 200),
            (6,  '2025-02', '/v1/embeddings',        'openai',   350000,       0,  0.3500,   520, 200),
            (7,  '2025-02', '/v1/chat/completions',  'anthropic', 70000,   22000,  0.8800,  1050, 200),
            (8,  '2025-02', '/v1/chat/completions',  'openai',    40000,    8000,  0.2800,   700, 429),
            (9,  '2025-03', '/v1/chat/completions',  'openai',   120000,   40000,  1.0400,  1300, 200),
            (10, '2025-03', '/v1/embeddings',        'openai',   500000,       0,  0.5000,   600, 200),
            (11, '2025-03', '/v1/chat/completions',  'anthropic', 90000,   28000,  1.1200,  1150, 200),
            (12, '2025-03', '/v1/chat/completions',  'openai',    55000,   15000,  0.4250,   850, 200),
            (13, '2025-04', '/v1/chat/completions',  'openai',   150000,   50000,  1.3000,  1400, 200),
            (14, '2025-04', '/v1/embeddings',        'openai',   650000,       0,  0.6500,   680, 200),
            (15, '2025-04', '/v1/chat/completions',  'anthropic',110000,   35000,  1.4500,  1250, 200),
            (16, '2025-04', '/v1/chat/completions',  'openai',    70000,   20000,  0.5500,   900, 500)
    """)

    return conn


# ==========================================
# QUERIES ANALÍTICAS REALES
# ==========================================

def query_costo_mensual_embeddings(conn: duckdb.DuckDBPyConnection) -> str:
    """Agregación mensual de costos de embedding."""
    result = conn.execute("""
        SELECT
            mes,
            modelo,
            SUM(documentos_procesados) AS total_docs,
            SUM(tokens_totales) AS total_tokens,
            ROUND(SUM(costo_usd), 4) AS costo_total_usd,
            ROUND(AVG(latencia_promedio_ms), 0) AS latencia_avg_ms
        FROM embedding_jobs
        GROUP BY mes, modelo
        ORDER BY mes, costo_total_usd DESC
    """).fetchall()

    lines = ["Mes       | Modelo                      | Docs  | Tokens     | Costo USD | Latencia ms"]
    lines.append("-" * 95)
    for row in result:
        lines.append(f"{row[0]}  | {row[1]:<27} | {row[2]:>5} | {row[3]:>10} | ${row[4]:>8.4f} | {row[5]:>6.0f}")
    return "\n".join(lines)


def query_top_api_calls(conn: duckdb.DuckDBPyConnection) -> str:
    """Top-5 llamadas API más costosas."""
    result = conn.execute("""
        SELECT
            call_id, mes, proveedor, endpoint,
            tokens_input + tokens_output AS tokens_totales,
            costo_usd, latencia_ms, status_code
        FROM api_calls
        ORDER BY costo_usd DESC
        LIMIT 5
    """).fetchall()

    lines = ["ID | Mes     | Proveedor  | Tokens Tot. | Costo USD | Latencia ms | Status"]
    lines.append("-" * 80)
    for row in result:
        lines.append(f"{row[0]:>2} | {row[1]}  | {row[2]:<10} | {row[4]:>11} | ${row[5]:>8.4f} | {row[6]:>6}      | {row[7]}")
    return "\n".join(lines)


def query_throughput_documentos(conn: duckdb.DuckDBPyConnection) -> str:
    """Throughput de procesamiento de documentos por mes."""
    result = conn.execute("""
        SELECT
            mes,
            SUM(documentos_procesados) AS total_docs,
            SUM(tokens_totales) AS total_tokens,
            ROUND(SUM(costo_usd), 4) AS costo_total,
            ROUND(SUM(costo_usd) / SUM(tokens_totales) * 1000000, 4) AS costo_por_millon_tokens
        FROM embedding_jobs
        GROUP BY mes
        ORDER BY mes
    """).fetchall()

    lines = ["Mes     | Docs  | Tokens     | Costo Total | $/1M Tokens"]
    lines.append("-" * 65)
    for row in result:
        lines.append(f"{row[0]}  | {row[1]:>5} | {row[2]:>10} | ${row[3]:>10.4f} | ${row[4]:>8.4f}")
    return "\n".join(lines)


def query_calidad_por_categoria(conn: duckdb.DuckDBPyConnection) -> str:
    """Score de calidad promedio por categoría de documento."""
    result = conn.execute("""
        SELECT
            categoria,
            COUNT(*) AS jobs,
            ROUND(AVG(calidad_score), 3) AS calidad_promedio,
            ROUND(MIN(calidad_score), 2) AS calidad_min,
            ROUND(MAX(calidad_score), 2) AS calidad_max,
            SUM(documentos_procesados) AS docs_totales
        FROM embedding_jobs
        GROUP BY categoria
        ORDER BY calidad_promedio DESC
    """).fetchall()

    lines = ["Categoría    | Jobs | Calidad Prom. | Mín  | Máx  | Docs Totales"]
    lines.append("-" * 70)
    for row in result:
        lines.append(f"{row[0]:<12} | {row[1]:>4} | {row[2]:>13.3f} | {row[3]:>4.2f} | {row[4]:>4.2f} | {row[5]:>6}")
    return "\n".join(lines)


def query_costo_por_token(conn: duckdb.DuckDBPyConnection) -> str:
    """Análisis de costo por token para llamadas API de chat."""
    result = conn.execute("""
        SELECT
            proveedor,
            endpoint,
            COUNT(*) AS llamadas,
            SUM(tokens_input) AS total_input,
            SUM(tokens_output) AS total_output,
            ROUND(SUM(costo_usd), 4) AS costo_total,
            ROUND(SUM(costo_usd) / (SUM(tokens_input) + SUM(tokens_output)) * 1000000, 4) AS costo_por_millon
        FROM api_calls
        WHERE status_code = 200
        GROUP BY proveedor, endpoint
        ORDER BY costo_por_millon DESC
    """).fetchall()

    lines = ["Proveedor  | Endpoint               | Llamadas | Input Tot. | Output Tot. | Costo Tot. | $/1M Tokens"]
    lines.append("-" * 100)
    for row in result:
        lines.append(f"{row[0]:<10} | {row[1]:<22} | {row[2]:>8} | {row[3]:>10} | {row[4]:>11} | ${row[5]:>8.4f} | ${row[6]:>8.4f}")
    return "\n".join(lines)


def ejecutar_queries_reales(conn: duckdb.DuckDBPyConnection):
    """Ejecuta todas las queries reales y muestra resultados."""

    print("\n" + "=" * 70)
    print("  CAPA DE DATOS: DuckDB en memoria — Queries analíticas reales")
    print("=" * 70)

    print("\n--- Query 1: Costo mensual de embeddings por modelo ---\n")
    print(query_costo_mensual_embeddings(conn))

    print("\n--- Query 2: Top-5 llamadas API más costosas ---\n")
    print(query_top_api_calls(conn))

    print("\n--- Query 3: Throughput de procesamiento de documentos ---\n")
    print(query_throughput_documentos(conn))

    print("\n--- Query 4: Score de calidad por categoría ---\n")
    print(query_calidad_por_categoria(conn))

    print("\n--- Query 5: Costo por token (solo llamadas exitosas) ---\n")
    print(query_costo_por_token(conn))


# ==========================================
# MODO MOCK (sin API Key o sin crewai)
# ==========================================

MOCK_ANALYST_OUTPUT = (
    "Tras analizar los datos de DuckDB, se observan las siguientes tendencias:\n\n"
    "1) El costo de embeddings creció de $3.55 en enero a $7.59 en abril (+113%), "
    "impulsado por el aumento de documentos procesados (de 2300 a 4580).\n"
    "2) El modelo text-embedding-3-large concentra el 60% del gasto total pese a "
    "representar solo el 15% de los documentos procesados.\n"
    "3) El throughput mensual muestra una tendencia lineal ascendente: "
    "de 8M tokens/mes en enero a 18.7M tokens/mes en abril.\n"
    "4) Anthropic tiene un costo por millón de tokens 2.3x mayor que OpenAI para chat completions."
)

MOCK_OPTIMIZER_OUTPUT = (
    "Recomendaciones de optimización de costos basadas en los datos reales:\n\n"
    "1) **Migrar embeddings de 'large' a 'small' para chunks**: La diferencia de calidad "
    "es solo 0.07 puntos (0.97 vs 0.90) pero el costo es 3.6x mayor. Ahorro estimado: $4.55/mes.\n"
    "2) **Eliminar text-embedding-ada-002**: Tiene el peor score de calidad (0.72-0.75) y "
    "representa menos del 1% del volumen. Consolidar en 3-small.\n"
    "3) **Implementar batching para API calls**: Las llamadas individuales a OpenAI tienen "
    "un overhead de latencia de ~200ms. Agrupar en lotes de 100 reduciría latencia un 40%.\n"
    "4) **Negociar tier de volumen con Anthropic**: Con 330K tokens/mes de output, "
    "se califica para un descuento del 15-20% en el plan Team."
)

MOCK_AUDITOR_OUTPUT = (
    "Auditoría de calidad de datos — Resultados:\n\n"
    "1) **Cobertura**: 14 jobs de embedding y 16 llamadas API registradas. Sin gaps temporales.\n"
    "2) **Anomalías detectadas**: 1 llamada con status 429 (rate limit) en febrero y "
    "1 llamada con status 500 (error de servidor) en abril. Tasa de error: 12.5%.\n"
    "3) **Calidad por categoría**: 'metadata' tiene el score más bajo (0.72-0.75), "
    "por debajo del umbral aceptable de 0.80. Requiere revisión del pipeline de extracción.\n"
    "4) **Consistencia**: Los costos por token son consistentes dentro de cada modelo. "
    "No se detectaron discrepancias entre tokens reportados y costos facturados.\n"
    "5) **Dictamen final**: Datos confiables para toma de decisiones. "
    "Acción requerida: mejorar pipeline de metadata y monitorear errores 5xx."
)


def run_mock_demo(conn: duckdb.DuckDBPyConnection, reason: str):
    """Ejecuta la demo con crew simulado pero queries DuckDB reales."""
    print(f"\n[NOTE] {reason}. Usando respuestas simuladas para el crew.\n")

    print("=" * 70)
    print("  DUCKDB + CREWAI DEMO — Equipo de Analítica de Operaciones IA")
    print("=" * 70)

    ejecutar_queries_reales(conn)

    print("\n" + "=" * 70)
    print("  CREW MULTI-AGENTE (modo simulado)")
    print("=" * 70)

    print("\n--- Paso 1: Analista de Datos consulta métricas y agregaciones ---")
    print(f"\n{MOCK_ANALYST_OUTPUT}")

    print("\n--- Paso 2: Optimizador de Costos analiza tokens y recomienda ahorros ---")
    print(f"\n{MOCK_OPTIMIZER_OUTPUT}")

    print("\n--- Paso 3: Auditor de Calidad verifica integridad y consistencia ---")
    print(f"\n{MOCK_AUDITOR_OUTPUT}")

    print("\n" + "=" * 70)
    print("  Resultado Final del Crew (Secuencial)")
    print("=" * 70)
    print(f"\n{MOCK_AUDITOR_OUTPUT}")


# ==========================================
# MODO EN VIVO (CrewAI + DuckDB real)
# ==========================================

def run_live_demo(conn: duckdb.DuckDBPyConnection):
    """Ejecuta la demo con CrewAI real consultando DuckDB."""
    api_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = api_key

    @tool("query_costo_embeddings")
    def query_costo_embeddings() -> str:
        """Consulta el costo mensual de embeddings por modelo en la base de datos DuckDB."""
        return query_costo_mensual_embeddings(conn)

    @tool("query_top_api_calls")
    def query_top_api_calls_tool() -> str:
        """Consulta las 5 llamadas API más costosas registradas en DuckDB."""
        return query_top_api_calls(conn)

    @tool("query_throughput")
    def query_throughput() -> str:
        """Consulta el throughput mensual de procesamiento de documentos en DuckDB."""
        return query_throughput_documentos(conn)

    @tool("query_calidad")
    def query_calidad() -> str:
        """Consulta el score de calidad promedio por categoría de documento en DuckDB."""
        return query_calidad_por_categoria(conn)

    @tool("query_costo_token")
    def query_costo_token() -> str:
        """Consulta el análisis de costo por token para llamadas API exitosas en DuckDB."""
        return query_costo_por_token(conn)

    data_analyst = Agent(
        role="Analista de Datos Senior",
        goal="Extraer métricas clave y tendencias de las operaciones de IA usando queries SQL a DuckDB.",
        backstory=(
            "Eres un analista de datos especializado en operaciones de ingeniería de IA. "
            "Dominas SQL analítico y entiendes métricas de embeddings, costos de tokens y "
            "throughput de procesamiento. Tu trabajo es consultar la base DuckDB y presentar "
            "hallazgos accionables."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gemini/gemini-2.0-flash",
        tools=[query_costo_embeddings, query_throughput, query_top_api_calls_tool],
    )

    cost_optimizer = Agent(
        role="Optimizador de Costos de IA",
        goal="Analizar costos de tokens y embeddings para recomendar estrategias de ahorro.",
        backstory=(
            "Eres un especialista en optimización de costos para infraestructura de IA. "
            "Analizas patrones de uso de APIs, costos por token, y eficiencia de modelos de "
            "embedding. Tu objetivo es identificar oportunidades de ahorro sin sacrificar calidad."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gemini/gemini-2.0-flash",
        tools=[query_costo_embeddings, query_costo_token, query_top_api_calls_tool],
    )

    quality_auditor = Agent(
        role="Auditor de Calidad de Datos",
        goal="Verificar la integridad, consistencia y calidad de los datos operacionales.",
        backstory=(
            "Eres un auditor de calidad enfocado en datos de operaciones de IA. "
            "Evalúas scores de calidad por categoría, detectas anomalías en llamadas API, "
            "y verificas que no existan gaps en los datos. Tu dictamen determina si los datos "
            "son confiables para la toma de decisiones."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gemini/gemini-2.0-flash",
        tools=[query_calidad, query_top_api_calls_tool, query_throughput],
    )

    task_analisis = Task(
        description=(
            "Consulta la base de datos DuckDB para obtener métricas de embeddings y throughput. "
            "Identifica tendencias de crecimiento, modelos más costosos y patrones de uso mensual. "
            "Presenta un resumen ejecutivo con los 3 hallazgos más relevantes."
        ),
        expected_output="Un resumen ejecutivo con 3 hallazgos clave sobre métricas de embeddings y throughput.",
        agent=data_analyst,
    )

    task_costos = Task(
        description=(
            "Usa los datos de DuckDB para analizar costos por token y costos de embeddings. "
            "Compara proveedores (OpenAI vs Anthropic) y modelos de embedding. "
            "Proporciona 3 recomendaciones concretas de ahorro con estimaciones de impacto."
        ),
        expected_output="3 recomendaciones de optimización de costos con ahorro estimado.",
        agent=cost_optimizer,
    )

    task_calidad = Task(
        description=(
            "Audita la calidad de los datos en DuckDB: revisa scores por categoría, "
            "detecta llamadas API con errores (status != 200), y verifica consistencia "
            "entre tokens y costos. Emite un dictamen final sobre la confiabilidad de los datos."
        ),
        expected_output="Un dictamen de calidad con anomalías detectadas y acciones requeridas.",
        agent=quality_auditor,
    )

    crew = Crew(
        agents=[data_analyst, cost_optimizer, quality_auditor],
        tasks=[task_analisis, task_costos, task_calidad],
        process=Process.sequential,
        verbose=True,
    )

    print("=" * 70)
    print("  DUCKDB + CREWAI DEMO — Equipo de Analítica de Operaciones IA")
    print("  (Modo en vivo con Gemini 2.0 Flash + DuckDB real)")
    print("=" * 70)

    ejecutar_queries_reales(conn)

    print("\n" + "=" * 70)
    print("  CREW MULTI-AGENTE (modo en vivo)")
    print("=" * 70)
    print("\nEjecutando crew.kickoff()...\n")

    result = crew.kickoff()

    print("\n" + "=" * 70)
    print("  Resultado Final del Crew")
    print("=" * 70)
    print(f"\n{result}")


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    print("Inicializando DuckDB en memoria con datos de operaciones de IA...")
    conn = crear_base_de_datos()

    row_count = conn.execute("SELECT COUNT(*) FROM embedding_jobs").fetchone()[0]
    api_count = conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0]
    print(f"DuckDB listo: {row_count} jobs de embedding, {api_count} llamadas API cargadas.")

    api_key = os.environ.get("GEMINI_API_KEY")

    if not CREWAI_AVAILABLE:
        run_mock_demo(conn, "crewai no pudo importarse (incompatibilidad de dependencias)")
    elif not api_key:
        run_mock_demo(conn, "No se encontró GEMINI_API_KEY")
    else:
        run_live_demo(conn)

    conn.close()
    print("\nConexión DuckDB cerrada. Demo finalizada.")
