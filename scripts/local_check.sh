#!/bin/bash
# scripts/local_check.sh
# Runs all local CI quality checks: ruff lint, mypy typecheck, tsc typecheck, and pytest.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting Local AI Lab Verification Suite ===${NC}\n"

# Install Git Pre-commit Hook if requested
if [ "$1" == "--install-hook" ]; then
    echo -e "${BLUE}[Git Hook] Installing pre-commit hook...${NC}"
    mkdir -p .git/hooks
    cp "$0" .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo -e "${GREEN}[Git Hook] Pre-commit hook successfully installed!${NC}\n"
    exit 0
fi

# 1. Ruff Lint check
echo -e "${BLUE}[1/4] Running Ruff Linter...${NC}"
if command -v uvx &> /dev/null; then
    uvx ruff check .
else
    pip install -q ruff
    ruff check .
fi
echo -e "${GREEN}✓ Linter passed successfully.${NC}\n"

# 2. Python Typecheck (Mypy)
echo -e "${BLUE}[2/4] Running Mypy Typechecker...${NC}"
if command -v uv &> /dev/null; then
    # Run mypy on primitives
    uv run --with mypy mypy 00_primitives_scratch/
else
    pip install -q mypy
    mypy 00_primitives_scratch/
fi
echo -e "${GREEN}✓ Python Typechecker passed successfully.${NC}\n"

# 3. TypeScript Typecheck (tsc)
echo -e "${BLUE}[3/4] Running TypeScript Typechecker...${NC}"
if [ -d "02_typescript_frameworks" ]; then
    cd 02_typescript_frameworks
    if command -v bun &> /dev/null; then
        bun x tsc --noEmit
    else
        npx tsc --noEmit
    fi
    cd ..
    echo -e "${GREEN}✓ TypeScript Typechecker passed successfully.${NC}\n"
else
    echo -e "${RED}✗ TypeScript frameworks directory not found! Skipping.${NC}\n"
fi

# 4. Automated Tests (Pytest)
echo -e "${BLUE}[4/4] Running Automated Tests...${NC}"
if command -v uv &> /dev/null; then
    uv run --project 01_python_frameworks --with pytest pytest tests/ -v
else
    pip install -q pytest
    pytest tests/ -v
fi
echo -e "${GREEN}✓ All tests passed successfully.${NC}\n"

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}🎉 All local checks passed! You are ready to commit.${NC}"
echo -e "${GREEN}==================================================${NC}"
