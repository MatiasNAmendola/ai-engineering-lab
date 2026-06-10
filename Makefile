.PHONY: check lint typecheck typecheck-ts test test-textbook test-primitives serve serve-textbook hook install-ts clean

check: lint typecheck typecheck-ts test

lint:
	uvx ruff check .

typecheck:
	uv run --with mypy mypy 00_primitives_scratch/

typecheck-ts:
	cd 02_typescript_frameworks && bun x tsc --noEmit

test:
	uv run --project 01_python_frameworks --with pytest pytest tests/ -v

test-textbook:
	uv run --project 01_python_frameworks --with pytest pytest tests/textbook_generator/ -v

test-primitives:
	uv run --project 01_python_frameworks --with pytest pytest tests/test_primitives.py -v

serve:
	uv run --project 01_python_frameworks python -m uvicorn textbook_generator.main:app --reload --port 8000

serve-textbook:
	uv run --project 01_python_frameworks python -m uvicorn textbook_generator.main:app --reload --port 8000

hook:
	bash scripts/local_check.sh --install-hook

install-ts:
	cd 02_typescript_frameworks && bun install

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
