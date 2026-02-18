FROM python:3.12-slim
WORKDIR /app

# System dependencies (WeasyPrint requires Pango, Mermaid CLI requires Node.js)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    && npm install -g @mermaid-js/mermaid-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --no-dev --no-editable --frozen

# Playbooks (loaded at runtime)
COPY playbooks/ ./playbooks/

RUN mkdir -p data logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "artifactor.main:app", "--host", "0.0.0.0", "--port", "8000"]
