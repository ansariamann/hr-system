#!/bin/bash

# Development startup script for ATS Backend

set -e

echo "Starting ATS Backend Development Environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please review and update .env file with your configuration"
fi

# Start services with Docker Compose
echo "Starting Docker services..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check if services are healthy
echo "Checking service health..."
docker-compose ps

echo "Development environment started!"
echo ""
echo "Services available:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "To start the API server:"
echo "  python -m uvicorn ats_backend.api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "To start Celery worker:"
echo "  python -m celery worker -A ats_backend.worker.celery_app --loglevel=info"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"