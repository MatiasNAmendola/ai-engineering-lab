# Generador de Libros de Texto Asistido por IA (Clean & Screaming Architecture)

Un sistema impulsado por IA diseñado para generar libros de texto de educación primaria (enfocados en 1° grado de primaria, K-12) alineados con **Lineamientos Curriculares Nacionales**.

La aplicación está estructurada siguiendo estrictamente las directrices de **Clean Architecture (Arquitectura Hexagonal / Puertos y Adaptadores)** y **Screaming Architecture** para aislar las reglas de negocio de los mecanismos de entrega, bases de datos y frameworks de IA.

---

## 🏗️ Patrones de Diseño Arquitectónicos

### 1. Capas (Clean Architecture)
*   **`domain/` (Dominio)**: El núcleo del sistema. Contiene las entidades puras (`Textbook`, `Trimestre`, `Secuencia`, `Lesson`, `CurricularRequirement`) y los puertos (`repositories.py` que abstrae el almacenamiento, `services.py` que abstrae los agentes de IA). No tiene dependencias de librerías externas (FastAPI, SQLAlchemy y PydanticAI están completamente ausentes aquí).
*   **`application/` (Aplicación)**: Lógica de orquestación de casos de uso. Coordina los flujos de datos del negocio usando las entidades y puertos del dominio. Desacoplada de implementaciones concretas mediante inyección de dependencias.
*   **`infrastructure/` (Infraestructura)**: Adaptadores concretos del sistema.
    *   `database/`: Persistencia en base de datos SQLite mediante SQLAlchemy ORM.
    *   `agents/`: Adaptadores de agentes estructurados implementados con **PydanticAI**.
    *   `http/`: Endpoints controladores REST expuestos mediante **FastAPI**.
    *   `static/`: Frontend Single Page App (SPA) con diseño premium glassmorphism oscuro.

### 2. Casos de Uso "Screaming" (Screaming Architecture)
El contenido de la carpeta `application/` está dividido en archivos independientes que representan de forma explícita las acciones de negocio del sistema, haciendo que la intención del software sea obvia a primera vista:
-   `create_textbook.py`: Inicializa un proyecto de libro en estado borrador.
-   `generate_book_outline.py`: Genera la macro-estructura (3 trimestres, 18 secuencias didácticas) mediante un agente.
-   `generate_sequence_content.py`: Genera el contenido de las lecciones (Inicio-Desarrollo-Cierre) y evalúa su calidad.
-   `generate_book_workflow.py`: Orquestador de segundo plano que corre la generación secuencial completa del libro.
-   `review_sequence.py`: Administra la cola de aprobación y dictamen humano (Human-in-the-Loop).

### 3. Guardrails & Human-in-the-Loop (HITL)
Cada secuencia didáctica generada pasa por la auditoría de un agente **LLM-as-a-Judge**. Si los puntajes de alineación curricular o adecuación de edad caen por debajo de **0.85/1.00**, la secuencia didáctica se deriva a la cola de revisión de la consola docente. Un pedagogo humano puede autorizar el texto o rechazarlo aportando comentarios, lo cual dispara una regeneración asistida por IA basada en su retroalimentación.

### 4. Registro de Decisiones Arquitectónicas (ADRs)
*   **ADR-001: PydanticAI sobre LangChain/LangGraph**: Elegimos PydanticAI por su tipado estático nativo y su nula "complejidad accidental" en comparación con LangChain (LCEL y stack traces complejos). LangGraph no se requiere ya que el workflow de generación de libros es una estructura lineal jerárquica (Libro -> Trimestre -> Secuencia -> Lección), sin ciclos complejos que justifiquen grafos de estado.
*   **ADR-002: SQLite sobre Base de Datos Vectorial Dedicada**: El catálogo de lineamientos curriculares para una asignatura/grado es muy pequeño (<100 registros). SQLite provee transacciones ACID nativas (compartiendo conexiones con las tablas operativas de la app) y búsquedas con latencias de microsegundos mediante filtros relacionales exactos, evitando la sobrecarga y costos de nube de un motor vectorial como Qdrant. El camino de escalado contempla **PostgreSQL + pgvector** para búsquedas híbridas a escala global.
*   **ADR-003: Estrategia de Caching en Producción**: No cacheamos lecciones completas para garantizar la diversidad didáctica entre escuelas y evitar la persistencia de alucinaciones. En su lugar, implementamos **LLM Prompt Caching (Context Caching en Gemini)** para mantener en memoria los tokens de lineamientos curriculares en el servidor de inferencia del LLM, ahorrando hasta un 80% en costos de llamadas de red.

---

## 🚀 Cómo Ejecutar la Aplicación

### 1. Iniciar el Servidor FastAPI
Asegúrate de estar en el directorio raíz del espacio de trabajo y ejecuta el servidor con `uv`:
```bash
uv run --with uvicorn --with fastapi --with pydantic-ai-slim --with sqlalchemy uvicorn textbook_generator.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Abrir la Consola Web
Abre tu navegador en `http://127.0.0.1:8000`. Verás el panel de control oscuro.

### 3. Sembrar la Base de Datos
Haz clic en **"Sembrar BD"** en la parte inferior de la barra de navegación para cargar el catálogo básico de lineamientos curriculares nacionales en la base de datos de SQLite.

### 4. Crear y Generar
Dirígete a **"Crear Libro"**, selecciona "Español", ingresa un título de proyecto y presiona **"Iniciar Generación"**. El workflow de agentes procesará la estructura e irá redactando el contenido de forma asíncrona.

---

## 🧪 Pruebas Automatizadas
Para ejecutar la suite de pruebas unitarias e integración en memoria que valida repositorios, casos de uso y endpoints API, corre:
```bash
uv run --with pytest --with httpx --with pydantic-ai-slim --with sqlalchemy pytest tests/textbook_generator/ -v
```

---

## 🔬 Smoke Tests (Pruebas de Humo)
Para ejecutar las pruebas de humo reales sobre el servidor en funcionamiento y verificar la conectividad de los endpoints y el procesamiento en segundo plano, abre otra terminal y ejecuta:
```bash
uv run --with httpx python tests/smoke_test_api.py
```
