# Contributing

## Requisitos

- Python 3.11+ con [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh) (para TypeScript)

## Setup

```bash
# Dependencias Python (se resuelven automáticamente con uv run)
uv run --project 01_python_frameworks python -c "print('ok')"

# Dependencias TypeScript
bun install --cwd 02_typescript_frameworks

# Instalar git pre-commit hook
make hook
# o manualmente:
bash scripts/local_check.sh --install-hook
```

## Comandos

```bash
make check          # Ejecuta todo: lint + typecheck + tests
make lint           # Ruff linter
make typecheck      # Mypy sobre 00_primitives_scratch/
make typecheck-ts   # tsc --noEmit sobre 02_typescript_frameworks/
make test           # Todos los tests (Pytest)
make test-textbook  # Solo tests del textbook generator
make serve          # Levanta la API del textbook generator (puerto 8000)
make clean          # Limpia caches
```

Tambien podes correr el pipeline completo directamente:

```bash
bash scripts/local_check.sh
```

## Estructura

```
00_primitives_scratch/   # Scripts base: inference, RAG, agents, evals
01_python_frameworks/    # Frameworks Python (PydanticAI, LangGraph, CrewAI, etc.)
02_typescript_frameworks/ # Frameworks TS (Mastra, Pi, Flue)
03_go_frameworks/        # Frameworks Go
textbook_generator/      # Clean Architecture: generador de libros SEP/NEM
tests/                   # Unit, integration, E2E, ATDD, browser (Playwright)
wiki/                    # Articulos compilados, ADRs, guias de diseño
raw/                     # Fuentes brutas (inmutable)
scripts/                 # CI local, deploy
```

## Convenciones

- Los archivos en `00_primitives_scratch/` son scripts standalone ejecutables con `uv run`.
- Los articulos en `wiki/` usan enlaces relativos y no contienen rutas absolutas.
- El `textbook_generator/` sigue Clean Architecture: domain, application, infrastructure.
- Los tests usan SQLite in-memory y mock agents (no requieren API keys).
- Docker Compose esta disponible para levantar PostgreSQL + pgvector + MCP servers.
