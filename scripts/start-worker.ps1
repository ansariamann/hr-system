# Start Celery Worker PowerShell Script
# This script starts the Celery worker with proper configuration

param(
    [string]$BrokerUrl = "redis://localhost:6379/0",
    [string]$ResultBackend = "redis://localhost:6379/0",
    [string]$LogLevel = "INFO",
    [int]$Concurrency = 4
)

Write-Host "Starting ATS Backend Celery Worker..." -ForegroundColor Green

# Set environment variables
$env:CELERY_BROKER_URL = $BrokerUrl
$env:CELERY_RESULT_BACKEND = $ResultBackend
$env:LOG_LEVEL = $LogLevel

# Check if Redis is available
Write-Host "Checking Redis connectivity..." -ForegroundColor Yellow
try {
    python -c "
import redis
r = redis.from_url('$BrokerUrl')
r.ping()
print('✓ Redis connection successful')
"
    Write-Host "✓ Redis connection successful" -ForegroundColor Green
} catch {
    Write-Host "✗ Redis connection failed: $_" -ForegroundColor Red
    exit 1
}

# Display configuration
Write-Host "Starting Celery worker with configuration:" -ForegroundColor Cyan
Write-Host "  Broker: $BrokerUrl" -ForegroundColor White
Write-Host "  Backend: $ResultBackend" -ForegroundColor White
Write-Host "  Log Level: $LogLevel" -ForegroundColor White
Write-Host "  Concurrency: $Concurrency" -ForegroundColor White
Write-Host "  Queues: resume_processing,email_processing" -ForegroundColor White

# Start Celery worker
python -m celery worker `
    -A ats_backend.workers.celery_app `
    --loglevel=$LogLevel `
    --concurrency=$Concurrency `
    --queues=resume_processing,email_processing `
    --hostname=worker@$env:COMPUTERNAME `
    --time-limit=600 `
    --soft-time-limit=300 `
    --max-tasks-per-child=1000 `
    --prefetch-multiplier=1