# Guía para Agentes de IA

Este documento proporciona instrucciones detalladas para agentes de IA que trabajan en el Textbook Generator.

## 🧪 Estrategia de Testing

### Pirámide de Tests

```
        /  E2E Browser (Playwright)  \       <- 20 tests, ~90s
       /  E2E API (httpx/requests)    \      <- Validación de endpoints
      /  Integration (DB + Services)   \     <- Flujos completos con SQLite
     /  Unit (funciones aisladas)       \    <- Lógica de negocio
```

### Comandos de Testing

**Todos los tests:**
```bash
uv run --project 01_python_frameworks pytest tests/textbook_generator/ -v
```

**Tests de browser (UI):**
```bash
# Primera vez: instalar Chromium
uv run --project 01_python_frameworks playwright install chromium

# Ejecutar tests de browser
uv run --project 01_python_frameworks --with pytest --with pytest-playwright --with requests \
  pytest tests/textbook_generator/browser/ -v
```

**Tests unitarios:**
```bash
uv run --project 01_python_frameworks pytest tests/textbook_generator/unit/ -v
```

**Tests de integración:**
```bash
uv run --project 01_python_frameworks pytest tests/textbook_generator/integration/ -v
```

**Linting:**
```bash
uv run --project 01_python_frameworks ruff check textbook_generator/ tests/
```

### Tests de Browser con Playwright

Los tests de browser validan la SPA navegando la interfaz real con Chromium headless.

**Arquitectura:**
- Servidor FastAPI auto-arranca en puerto efímero (configurado en `conftest.py`)
- Base de datos SQLite temporal (aislada de desarrollo)
- Fixture `server_url` provee la URL base para todos los tests
- Fixture `seeded_page` crea un libro de prueba antes de cada test

**Estructura de archivos:**
```
tests/textbook_generator/browser/
├── conftest.py              # Setup de servidor y fixtures
└── test_browser_e2e.py      # 20 tests organizados por flujo
```

**Cuándo ejecutar tests de browser:**
- ✅ Después de modificar `textbook_generator/static/` (HTML, CSS, JS)
- ✅ Después de cambiar flujos de usuario (crear libro, revisar secuencia, etc.)
- ✅ Después de agregar nuevos endpoints que afecten la UI
- ❌ No necesario para cambios en backend puro que no exponen UI

**Troubleshooting:**
- Si los tests fallan con "Timeout exceeded": verificar que Chromium esté instalado
- Si fallan aleatoriamente: puede ser timing, aumentar timeouts en `conftest.py`
- Ver logs del servidor en la consola donde corrieron los tests

## 📁 Estructura del Proyecto

```
textbook_generator/
├── domain/                    # Modelos de dominio (NEM, Secuencia, Lesson)
│   ├── models.py
│   ├── repositories.py        # Interfaces abstractas
│   └── services.py            # DTOs y contratos de agentes
├── application/               # Casos de uso
│   ├── generate_book_workflow.py
│   ├── export_conaliteg_format.py
│   ├── contextualize_textbook.py
│   └── ...
├── infrastructure/            # Implementaciones concretas
│   ├── database/
│   │   ├── db_models.py       # Modelos SQLAlchemy
│   │   └── repositories.py    # Implementaciones SQLite
│   └── agents/
│       ├── pydantic_agents.py # Agentes de IA (Gemini, mock mode)
│       └── nem_agents.py      # Agentes especializados NEM
└── static/                    # Frontend SPA
    ├── index.html
    ├── styles.css
    └── app.js
```

## 🏗️ Convenciones de Código

### Domain-Driven Design
- **Domain**: Lógica pura sin dependencias externas
- **Application**: Orquestación de casos de uso
- **Infrastructure**: Detalles técnicos (DB, APIs, agentes)

### NEM (Nueva Escuela Mexicana)
El dominio está alineado con el currículo educativo mexicano:
- **Campos Formativos**: 4 ejes transversales (Lenguajes, Saberes Científicos, Ética, De lo Humano)
- **Ejes Articuladores**: 7 temas transversales (Inclusión, Pensamiento Crítico, etc.)
- **Fases de Aprendizaje**: 6 fases, FASE_2 = Primaria 1°-2°
- **Contenidos Sintéticos**: Objetivos de aprendizaje oficiales SEP
- **PDAs (Procesos de Desarrollo de Aprendizaje)**: Competencias específicas

### Nombres y Estilo
- **Español**: La mayoría de nombres de dominio en español (Secuencia, Lección, Trimestre)
- **CamelCase**: Clases y tipos
- **snake_case**: Funciones, variables, nombres de archivos
- **CONSTANTES**: Solo para enums y configuración

## 🔧 Comandos Comunes

**Iniciar servidor de desarrollo:**
```bash
uv run --project 01_python_frameworks uvicorn textbook_generator.main:app --reload
```

**Sembrar base de datos:**
```bash
# Datos NEM Fase 2
uv run --project 01_python_frameworks python -m textbook_generator.infrastructure.seed_nem_fase2

# Curricular requirements (mock)
curl -X POST http://localhost:8000/api/admin/requirements/populate
```

**Ejecutar con export CONALITEG:**
```bash
uv run --project 01_python_frameworks python -m textbook_generator.application.export_conaliteg_format --textbook_id 1
```

## 🤖 Modo Mock de Agentes

Los agentes de IA (PydanticAI con Gemini) tienen un **modo mock** para testing:
- Si `GEMINI_API_KEY` no está configurada, usan respuestas predefinidas
- Esto permite tests determinísticos sin llamadas a API
- El modo mock está en `pydantic_agents.py` y `nem_agents.py`

**Para tests unitarios/integración:**
```bash
# Sin API key = modo mock
uv run --project 01_python_frameworks pytest tests/textbook_generator/ -v
```

**Para tests reales con Gemini:**
```bash
export GEMINI_API_KEY="tu-api-key"
uv run --project 01_python_frameworks pytest tests/ -v
```

## 📝 Reglas para Modificar Código

1. **Siempre ejecutar tests después de cambios:**
   ```bash
   uv run --project 01_python_frameworks pytest tests/textbook_generator/ -v
   uv run --project 01_python_frameworks ruff check textbook_generator/ tests/
   ```

2. **Después de modificar frontend, ejecutar tests de browser:**
   ```bash
   uv run --project 01_python_frameworks --with pytest --with pytest-playwright --with requests \
     pytest tests/textbook_generator/browser/ -v
   ```

3. **Mantener inmutabilidad en Domain:**
   - Los modelos de dominio no deben tener side effects
   - La lógica de negocio debe ser testeable en aislamiento

4. **Respetar la arquitectura en capas:**
   - Domain → Application → Infrastructure (nunca al revés)
   - No importar `infrastructure` desde `domain` o `application`

5. **Documentar decisiones arquitectónicas:**
   - Cambios significativos deben documentarse en `wiki/` con formato ADR
   - Ejemplo: `wiki/11_adr_004_nem_integration.md`

## 🚨 Problemas Comunes

**"Cannot import name 'X'":**
- Verificar que el archivo existe y no fue revertido por el editor
- Limpiar cache: `find . -name "__pycache__" -type d -exec rm -rf {} +`

**"Database is locked":**
- Cerrar cualquier servidor FastAPI corriendo
- Eliminar `textbook_generator.db` si está corrupto

**Tests de browser fallan con timeout:**
- Verificar Chromium instalado: `uv run --project 01_python_frameworks playwright install chromium`
- Aumentar timeout en `conftest.py` si necesario
- Verificar que no hay otro servidor en el mismo puerto

**Ruff reporta errores:**
- Ejecutar auto-fix: `uv run --project 01_python_frameworks ruff check --fix textbook_generator/ tests/`

## 📚 Recursos Adicionales

- [Wiki del Proyecto](wiki/) - Documentación técnica y ADRs
- [ADR-004: Integración NEM](wiki/11_adr_004_nem_integration.md) - Decisiones de diseño NEM
- [Playwright Docs](https://playwright.dev/python/) - Documentación oficial
- [PydanticAI Docs](https://docs.pydantic.dev/ai/) - Framework de agentes
