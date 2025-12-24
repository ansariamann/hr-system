#!/bin/bash

# Start Celery Worker Script
# This script starts the Celery worker with proper configuration

set -e

echo "Starting ATS Backend Celery Worker..."

# Set default environment variables if not provided
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}

# Check if Redis is available
echo "Checking Redis connectivity..."
python -c "
import redis
import sys
try:
    r = redis.from_url('$CELERY_BROKER_URL')
    r.ping()
    print('✓ Redis connection successful')
except Exception as e:
    print(f'✗ Redis connection failed: {e}')
    sys.exit(1)
"

# Start Celery worker
echo "Starting Celery worker with configuration:"
echo "  Broker: $CELERY_BROKER_URL"
echo "  Backend: $CELERY_RESULT_BACKEND"
echo "  Log Level: $LOG_LEVEL"
echo "  Queues: resume_processing,email_processing"

exec python -m celery worker \
    -A ats_backend.workers.celery_app \
    --loglevel=$LOG_LEVEL \
    --concurrency=4 \
    --queues=resume_processing,email_processing \
    --hostname=worker@%h \
    --time-limit=600 \
    --soft-time-limit=300 \
    --max-tasks-per-child=1000 \
    --prefetch-multiplier=1