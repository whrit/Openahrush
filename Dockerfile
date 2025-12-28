# Multi-stage Dockerfile for Openahrush API
# Builds a production-ready Python 3.12 application with proper security hardening

# Stage 1: Builder
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

# Install system dependencies required for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set PATH to include uv
ENV PATH="/root/.cargo/bin:$PATH"

# Copy workspace files
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY apps/ ./apps/
COPY migrations/ ./migrations/

# Install all dependencies with uv
RUN uv sync --frozen --no-cache

# Stage 2: Runtime
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/workspace/.venv/bin:$PATH" \
    VIRTUAL_ENV="/workspace/.venv"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /workspace/.venv /workspace/.venv

# Copy application code
COPY --from=builder --chown=appuser:appuser /workspace /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER appuser

# Health check - can be overridden by docker-compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose API port
EXPOSE 8000

# Run uvicorn server
# This assumes the api package has a main.py with an 'app' FastAPI instance
CMD ["uvicorn", "semrush_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
