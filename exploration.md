# Exploration: Infrastructure & Developer Experience Improvements

## Change Name: `infrastructure-improvements`

### Current State

The project is an AI Engineering Lab with:
- **5 Primitives** in `00_primitives_scratch/`: LLM inference, RAG/PGVector, Agent Runtime, Observability, Governance
- **Multiple MCP demos** in `01_python_frameworks/`: Basic MCP, Educational Platform, Virtual Wallet
- **Partial test coverage** - only `test_01_llm_inference.py` exists; imports for other tests fail
- **No Docker/Compose** - PGVector and MCP servers run locally
- **No CI/CD** - No GitHub Actions or local pre-commit hooks
- **README exists** with Mermaid diagram but no badges
- **No deploy scripts** for MCP servers

### Affected Areas

| Path | Reason |
|------|--------|
| `tests/` | Add missing test files for primitives 2-5 and MCP demos |
| `00_primitives_scratch/*.py` | Ensure primitives are testable (some need minor refactoring) |
| `01_python_frameworks/mcp_educational_platform_demo.py` | Add test entry points |
| `01_python_frameworks/mcp_demo.py` | Add test entry points |
| `pyproject.toml` | Add test dependencies, tool configs (ruff, mypy, pytest) |
| `docker-compose.yml` | **New file** - PGVector, MCP servers, demo |
| `Dockerfile` | **New file** - Containerize MCP educational server |
| `.github/workflows/ci.yml` | **New file** - CI pipeline (documented as not used due to cost) |
| `.pre-commit-config.yaml` | **New file** - Local hooks (ruff, mypy, pytest) |
| `README.md` | Add badges, improve Mermaid rendering |
| `deploy/*.sh` | **New files** - Deploy scripts for Railway/Fly/Cloud Run |
| `Makefile` | **New file** - Common commands |

### Approaches

#### 1. Tests: Complete test suite for all primitives + MCP demos
- **Approach A**: Write standalone test files per module (current pattern)
  - Pros: Follows existing pattern, isolated, easy to run
  - Cons: Some primitives need refactoring to be testable (global state)
  - Effort: Medium
- **Approach B**: Refactor primitives to be dependency-injectable then test
  - Pros: Better architecture, proper unit tests
  - Cons: More invasive changes to working code
  - Effort: High
- **Recommendation**: Approach A with minimal refactoring (make singletons resettable)

#### 2. Docker/Compose: Full stack orchestration
- **Approach A**: Single docker-compose with PGVector, MCP servers, test runner
  - Pros: One command starts everything, good for demos
  - Cons: Large compose file
  - Effort: Medium
- **Approach B**: Separate compose files per service + override
  - Pros: Modular, production-like
  - Cons: More complex
  - Effort: High
- **Recommendation**: Approach A - single `docker-compose.yml` with profiles for dev/test/demo

#### 3. CI/CD: Local-first with GitHub Actions documented as optional
- **Approach A**: pre-commit hooks + Makefile targets (no GitHub Actions)
  - Pros: Zero cost, runs locally, fast feedback
  - Cons: Not enforced on push
  - Effort: Low
- **Approach B**: GitHub Actions + pre-commit (user said NO to GH Actions due to cost)
  - Pros: Enforced on PR
  - Cons: Costs money, user explicitly rejected
  - Effort: Medium
- **Recommendation**: Approach A - Document clearly why no GitHub Actions

#### 4. README: Visual improvements
- Add shields.io badges for Python version, license, ruff, mypy, pytest
- Ensure Mermaid diagrams render on GitHub (they do natively)
- Add architecture diagram for MCP educational platform

#### 5. Deploy: Scripts for major platforms
- **Railway**: `railway up` with Dockerfile
- **Fly.io**: `fly deploy` with fly.toml
- **Cloud Run**: `gcloud run deploy` with Dockerfile
- Provide a unified deploy script with platform selection

### Recommendation

Implement in this order:
1. **Tests** - Foundation for everything else
2. **Docker/Compose** - Enables consistent test environment
3. **Local CI (pre-commit + Makefile)** - Developer workflow
4. **README badges** - Visual polish
5. **Deploy scripts** - Demo distribution

### Risks

- Some primitives use class-level state (TraceSpan.active_span_stack) - need reset methods
- MCP demos require API keys for full testing - need mock modes
- Docker compose needs PGVector image (pgvector/pgvector:pg16)
- Deploy scripts need platform CLIs installed

### Ready for Proposal

**Yes** - Clear scope, identified files, recommended approaches.