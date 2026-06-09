# Proposal: project-polish-and-ci

## Intent

Polish the AI Engineering Lab repository for public showcase by adding automated tests, Docker/Compose setup, local CI/CD tooling, visual README enhancements, and deployment scripts for the educational MCP server. This transforms the repo from a learning sandbox into a production-ready demonstration of AI engineering best practices.

## Scope

### In Scope (5 Workstreams)

1. **Tests Automatizados**: Comprehensive pytest coverage for all 5 primitives in `00_primitives_scratch/` + 2 MCP demos (`sqlite_mcp_server_demo.py`, `mcp_virtual_wallet_demo.py`). Tests run via `uv run pytest`.

2. **Docker/Compose**: `docker-compose.yml` with PostgreSQL+pgvector (pgvector/pgvector image), MCP servers (sqlite + virtual wallet as MCP servers), and an end-to-end demo script.

3. **CI/CD Local-First**: Pre-commit hooks (pre-commit framework), lint (ruff), typecheck (mypy), tests (pytest), build verification. Document in CONTRIBUTING.md why GitHub Actions is NOT used (cost concerns).

4. **README Visual**: Shields.io badges (Python versions, License MIT, CI status local, Project status), ensure Mermaid diagrams render on GitHub, visual improvements.

5. **Deploy Demo**: Deploy scripts for `sqlite_mcp_server_demo.py` to Railway (railway.toml), Fly.io (fly.toml), Google Cloud Run (Dockerfile + deploy script).

### Out of Scope

- GitHub Actions workflows (explicitly excluded per user request)
- Production-grade Kubernetes manifests
- Full test coverage for all 15+ framework demos (only 2 MCP demos)
- Authentication/authorization in deployed MCP servers
- Database migration tooling

## Approach

**Phase 1: Tests** (Foundation) - Add test files for primitives 2-5 and 2 MCP demos. Minimal refactoring to make singletons resettable.

**Phase 2: Docker/Compose** (Infrastructure) - Single docker-compose.yml with profiles for dev/test/demo. Use pgvector/pgvector:pg16 image.

**Phase 3: Local CI/CD** (Developer Workflow) - pre-commit-config.yaml with ruff, mypy, pytest; Makefile for common commands; CONTRIBUTING.md documenting no-GitHub-Actions decision.

**Phase 4: README Polish** (Visual) - Add badges, verify Mermaid rendering, add architecture diagram for MCP platform.

**Phase 5: Deploy Scripts** (Distribution) - Platform-specific configs and unified deploy script with platform selection.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/` | New/Modified | Add test_02_rag_pgvector.py, test_03_agent_runtime.py, test_04_observability.py, test_05_governance.py, test_mcp_servers.py |
| `00_primitives_scratch/*.py` | Modified | Add reset methods to singleton classes (TraceSpan.active_span_stack, etc.) |
| `01_python_frameworks/mcp_educational_platform_demo.py` | Modified | Add test entry points, mock modes |
| `01_python_frameworks/mcp_virtual_wallet_demo.py` | Modified | Add test entry points, mock modes |
| `01_python_frameworks/pyproject.toml` | Modified | Add test dependencies (pytest, pytest-asyncio, pytest-mock), tool configs |
| `docker-compose.yml` | New | Full stack: PGVector, MCP servers, demo runner |
| `Dockerfile` | New | Containerize MCP educational server |
| `.pre-commit-config.yaml` | New | Local hooks: ruff, mypy, pytest |
| `Makefile` | New | Common commands: test, lint, typecheck, build, up, down |
| `CONTRIBUTING.md` | New | Document local-first CI, why no GitHub Actions |
| `README.md` | Modified | Add badges, improve diagrams |
| `deploy/` | New | railway.toml, fly.toml, Dockerfile.cloudrun, deploy.sh |
| `CLAUDE.md` | Modified | Update with new conventions if needed |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Primitives use class-level state (TraceSpan.active_span_stack) | High | Add `reset()` classmethods to all singleton state holders |
| MCP demos require API keys for full testing | Medium | Add mock mode / dry-run flag to demos |
| Docker compose PGVector image version conflicts | Low | Pin to pgvector/pgvector:pg16 |
| Deploy scripts need platform CLIs installed | Medium | Document prerequisites, provide install hints |
| uv/bun/go version mismatches in CI | Low | Pin versions in tool configs |
| Mermaid not rendering on GitHub | Low | GitHub supports Mermaid natively; verify syntax |

## Rollback Plan

1. Delete new files: `docker-compose.yml`, `Dockerfile`, `.pre-commit-config.yaml`, `Makefile`, `CONTRIBUTING.md`, `deploy/`
2. Revert modifications to: `tests/`, `00_primitives_scratch/*.py`, `01_python_frameworks/*.py`, `pyproject.toml`, `README.md`, `CLAUDE.md`
3. Run `uv sync` to restore original dependencies
4. `git checkout -- .` from clean state

## Dependencies

- uv (Python package manager) - already used
- bun (TypeScript) - already used  
- go (Go) - already used
- pre-commit framework (new)
- pytest, pytest-asyncio, pytest-mock (new test deps)
- ruff, mypy (new lint/typecheck deps)
- Docker & Docker Compose (for local stack)
- Platform CLIs: railway, flyctl, gcloud (for deployment)

## Success Criteria

- [ ] `uv run pytest tests/` passes with >80% coverage on primitives + 2 MCP demos
- [ ] `docker-compose up -d` starts PGVector + both MCP servers + demo runner successfully
- [ ] `pre-commit run --all-files` passes (ruff, mypy, pytest)
- [ ] `make test` && `make lint` && `make typecheck` all succeed
- [ ] README.md displays badges and renders Mermaid diagrams on GitHub
- [ ] `./deploy.sh railway` deploys sqlite_mcp_server_demo.py to Railway
- [ ] `./deploy.sh fly` deploys to Fly.io
- [ ] `./deploy.sh cloudrun` deploys to Google Cloud Run
- [ ] CONTRIBUTING.md clearly documents local-first CI rationale