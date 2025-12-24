#!/bin/bash

# Start Celery Flower Monitoring Script
# This script starts Celery Flower for monitoring tasks and workers

set -e

echo "Starting ATS Backend Celery Flower Monitoring..."

# Set default environment variables if not provided
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}
export FLOWER_PORT=${FLOWER_PORT:-"5555"}

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

# Start Celery Flower
echo "Starting Celery Flower with configuration:"
echo "  Broker: $CELERY_BROKER_URL"
echo "  Backend: $CELERY_RESULT_BACKEND"
echo "  Port: $FLOWER_PORT"
echo "  URL: http://localhost:$FLOWER_PORT"

exec python -m celery flower \
    -A ats_backend.workers.celery_app \
    --port=$FLOWER_PORT \
    --broker=$CELERY_BROKER_URL \
    --basic_auth=admin:admin123 \
    --url_prefix=flower