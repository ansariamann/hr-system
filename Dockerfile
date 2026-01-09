# Multi-stage Dockerfile for ATS Backend System
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements
COPY pyproject.toml ./

# Install Python dependencies
# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -e .[dev]
COPY .env.example ./.env

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs

# API Stage
FROM base as api

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "ats_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Worker Stage
FROM base as worker

CMD ["python", "-m", "celery", "-A", "ats_backend.workers.celery_app", "worker", "--loglevel=info", "--concurrency=4", "--queues=resume_processing,email_processing"]

# Flower Stage (for monitoring)
FROM base as flower

EXPOSE 5555

CMD ["python", "-m", "celery", "-A", "ats_backend.workers.celery_app", "flower", "--port=5555"]