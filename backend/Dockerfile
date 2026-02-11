# Multi-stage build for production backend
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files
COPY pyproject.toml ./
COPY shared ./shared
COPY backend ./backend
COPY worker ./worker

# Install dependencies (production only)
RUN uv sync --package etl-backend --no-dev

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy uv from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy installed packages and workspace
COPY --from=builder /build/.venv /app/.venv
COPY pyproject.toml ./
COPY shared ./shared
COPY backend ./backend
COPY worker ./worker

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create storage directory and set permissions
RUN mkdir -p /app/backend/storage/uploads && \
    chown -R appuser:appuser /app

WORKDIR /app/backend

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
