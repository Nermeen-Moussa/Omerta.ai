# Omerta.ai backend (Phase 18): single-stage image with uv-managed deps.
FROM python:3.12-slim

WORKDIR /app

# Install uv, then the project (uv.lock guarantees reproducible deps).
COPY pyproject.toml uv.lock .python-version ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Application code (models/ ships the trained LightGBM artifact).
COPY alembic.ini ./
COPY apps ./apps
COPY domain ./domain
COPY infrastructure ./infrastructure
COPY mcp_servers ./mcp_servers
COPY migrations ./migrations
COPY scripts ./scripts
COPY models ./models

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Migrate + seed + project + ingest knowledge happen via explicit commands
# (see README) so a clean environment is reproducible without hidden steps.
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
