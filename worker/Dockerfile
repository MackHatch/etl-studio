# Multi-stage build for production worker
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
RUN uv sync --package etl-worker --no-dev

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

# Set permissions
RUN chown -R appuser:appuser /app

WORKDIR /app/worker

# So that file_path (storage/uploads/...) resolves: root = /app/backend
ENV UPLOAD_ROOT=/app/backend

USER appuser

CMD ["uv", "run", "celery", "-A", "worker_main.celery_app", "worker", "--loglevel=INFO", "--concurrency=2"]
