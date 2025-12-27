# ATS Backend CLI - PowerShell equivalent of Makefile commands
param(
    [Parameter(Position=0)]
    [string]$Command,
    
    [Parameter(Position=1)]
    [string]$Environment,
    
    [Parameter(Position=2)]
    [string]$BackupId,
    
    [switch]$Force,
    [switch]$Json,
    [switch]$Help
)

function Show-Help {
    Write-Host "ATS Backend CLI - Available Commands:" -ForegroundColor Green
    Write-Host ""
    Write-Host "Environment Management:" -ForegroundColor Yellow
    Write-Host "  deploy-dev          Deploy development environment"
    Write-Host "  deploy-staging      Deploy staging environment"
    Write-Host "  deploy-prod         Deploy production environment"
    Write-Host "  stop-dev            Stop development environment"
    Write-Host "  stop-staging        Stop staging environment"
    Write-Host "  stop-prod           Stop production environment"
    Write-Host "  env-status          Show status of all environments"
    Write-Host "  env-cleanup         Clean up all environments"
    Write-Host ""
    Write-Host "Disaster Recovery:" -ForegroundColor Yellow
    Write-Host "  backup-create       Create database backup"
    Write-Host "  backup-restore      Restore from backup (requires -BackupId)"
    Write-Host "  backup-list         List available backups"
    Write-Host "  backup-cleanup      Clean up old backups"
    Write-Host "  backup-status       Show disaster recovery status"
    Write-Host ""
    Write-Host "Testing:" -ForegroundColor Yellow
    Write-Host "  test                Run property-based tests"
    Write-Host "  test-unit           Run unit tests only"
    Write-Host "  test-property       Run property-based tests only"
    Write-Host "  test-all            Run all tests"
    Write-Host ""
    Write-Host "One-Command Operations:" -ForegroundColor Yellow
    Write-Host "  quick-deploy        Deploy complete dev environment (under 15 min)"
    Write-Host "  prod-deploy         Deploy production with full verification"
    Write-Host "  dr-test             Test disaster recovery procedures"
    Write-Host "  validate            Validate deployment (requires -Environment)"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  .\scripts\ats-cli.ps1 deploy-dev"
    Write-Host "  .\scripts\ats-cli.ps1 backup-restore -BackupId 20231226_120000"
    Write-Host "  .\scripts\ats-cli.ps1 validate -Environment dev"
    Write-Host "  .\scripts\ats-cli.ps1 prod-deploy -Force"
}

function Invoke-Command-Safe {
    param([string]$CommandLine)
    
    Write-Host "Executing: $CommandLine" -ForegroundColor Gray
    Invoke-Expression $CommandLine
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Command failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Show help if no command or help requested
if (-not $Command -or $Help) {
    Show-Help
    exit 0
}

# Execute commands
switch ($Command.ToLower()) {
    "deploy-dev" {
        Invoke-Command-Safe "python scripts/deploy_environment.py deploy dev"
    }
    "deploy-staging" {
        Invoke-Command-Safe "python scripts/deploy_environment.py deploy staging"
    }
    "deploy-prod" {
        $forceFlag = if ($Force) { "--force" } else { "" }
        Invoke-Command-Safe "python scripts/deploy_environment.py deploy prod $forceFlag"
    }
    "stop-dev" {
        Invoke-Command-Safe "python scripts/deploy_environment.py stop dev"
    }
    "stop-staging" {
        Invoke-Command-Safe "python scripts/deploy_environment.py stop staging"
    }
    "stop-prod" {
        Invoke-Command-Safe "python scripts/deploy_environment.py stop prod"
    }
    "env-status" {
        Invoke-Command-Safe "python scripts/deploy_environment.py status"
    }
    "env-cleanup" {
        Invoke-Command-Safe "python scripts/deploy_environment.py cleanup"
    }
    "backup-create" {
        Invoke-Command-Safe "python scripts/backup_database.py create"
    }
    "backup-restore" {
        if (-not $BackupId) {
            Write-Host "❌ BackupId is required for restore command" -ForegroundColor Red
            Write-Host "Usage: .\scripts\ats-cli.ps1 backup-restore -BackupId <backup_id>"
            exit 1
        }
        Invoke-Command-Safe "python scripts/backup_database.py restore $BackupId"
    }
    "backup-list" {
        Invoke-Command-Safe "python scripts/backup_database.py list"
    }
    "backup-cleanup" {
        Invoke-Command-Safe "python scripts/backup_database.py cleanup"
    }
    "backup-status" {
        Invoke-Command-Safe "python scripts/backup_database.py status"
    }
    "test" {
        $env:HYPOTHESIS_PROFILE = "production_hardening"
        Invoke-Command-Safe "pytest tests/property_based/ -m property_test -v"
    }
    "test-unit" {
        Invoke-Command-Safe "pytest tests/ -m unit -v"
    }
    "test-property" {
        $env:HYPOTHESIS_PROFILE = "production_hardening"
        Invoke-Command-Safe "pytest tests/property_based/ -m property_test -v"
    }
    "test-all" {
        Invoke-Command-Safe "pytest tests/ -v"
    }
    "quick-deploy" {
        Write-Host "🚀 Starting quick deployment..." -ForegroundColor Green
        Write-Host "⏱️  Target: Complete deployment in under 15 minutes" -ForegroundColor Yellow
        
        Invoke-Command-Safe "python scripts/deploy_environment.py cleanup"
        Invoke-Command-Safe "python scripts/deploy_environment.py deploy dev"
        Invoke-Command-Safe "python scripts/backup_database.py create"
        
        Write-Host "✅ Quick deployment completed!" -ForegroundColor Green
    }
    "prod-deploy" {
        Write-Host "🚀 Starting production deployment..." -ForegroundColor Green
        Write-Host "⚠️  This will deploy to production - ensure you have proper authorization" -ForegroundColor Red
        
        if (-not $Force) {
            $confirm = Read-Host "Continue with production deployment? [y/N]"
            if ($confirm -ne "y") {
                Write-Host "Production deployment cancelled" -ForegroundColor Yellow
                exit 0
            }
        }
        
        Invoke-Command-Safe "python scripts/backup_database.py create"
        Invoke-Command-Safe "python scripts/deploy_environment.py deploy prod --force"
        Invoke-Command-Safe "python scripts/backup_database.py create"
        
        Write-Host "✅ Production deployment completed!" -ForegroundColor Green
    }
    "dr-test" {
        Write-Host "🧪 Testing disaster recovery procedures..." -ForegroundColor Green
        
        Invoke-Command-Safe "python scripts/backup_database.py create"
        Invoke-Command-Safe "python scripts/backup_database.py list"
        Invoke-Command-Safe "python scripts/backup_database.py status"
        
        Write-Host "✅ Disaster recovery test completed!" -ForegroundColor Green
    }
    "validate" {
        if (-not $Environment) {
            Write-Host "❌ Environment is required for validate command" -ForegroundColor Red
            Write-Host "Usage: .\scripts\ats-cli.ps1 validate -Environment <dev|staging|prod>"
            exit 1
        }
        
        $jsonFlag = if ($Json) { "--json" } else { "" }
        Invoke-Command-Safe "python scripts/validate_deployment.py $Environment $jsonFlag"
    }
    default {
        Write-Host "❌ Unknown command: $Command" -ForegroundColor Red
        Write-Host "Use -Help to see available commands"
        exit 1
    }
}