FROM python:3.14-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

# Copy dependency files first (for Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen uses lockfile for reproducibility)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application
COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Final sync to install the project itself
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
