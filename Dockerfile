FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package installations
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency configuration first to cache layer
COPY 01_python_frameworks/pyproject.toml ./01_python_frameworks/

# Install python dependencies system-wide inside the container
RUN uv pip install --system -r 01_python_frameworks/pyproject.toml

# Copy project source code
COPY . .

# Expose default port for MCP SSE hosting
EXPOSE 8000

# Default entry point: Run educational MCP server in stdio mode
CMD ["python3", "01_python_frameworks/mcp_educational_platform_demo.py"]
