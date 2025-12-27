# Disaster Recovery and Environment Management

This document describes the disaster recovery and environment management capabilities implemented for the ATS Backend production hardening.

## Overview

The disaster recovery system provides:

- **Automated Database Backups** with configurable schedules
- **Verified Restore Testing** with integrity validation
- **Environment Separation** (dev, staging, production)
- **One-Command Deployment** with RTO guarantees
- **Recovery Time Objective (RTO) Compliance** monitoring

## Recovery Time Objectives (RTO)

The system enforces different RTO requirements based on environment:

| Environment | Backup Frequency | Max Data Loss (RPO) | Max Recovery Time (RTO) | Verification Frequency |
| ----------- | ---------------- | ------------------- | ----------------------- | ---------------------- |
| Development | 60 minutes       | 60 minutes          | 15 minutes              | 24 hours               |
| Staging     | 30 minutes       | 30 minutes          | 10 minutes              | 12 hours               |
| Production  | 15 minutes       | 15 minutes          | 5 minutes               | 6 hours                |

## Quick Start

### Using PowerShell CLI (Windows)

```powershell
# Show all available commands
.\scripts\ats-cli.ps1 -Help

# Deploy development environment (under 15 minutes)
.\scripts\ats-cli.ps1 quick-deploy

# Create a backup
.\scripts\ats-cli.ps1 backup-create

# Check disaster recovery status
.\scripts\ats-cli.ps1 backup-status

# Validate deployment
.\scripts\ats-cli.ps1 validate -Environment dev
```

### Using Make (Linux/macOS)

```bash
# Deploy development environment
make quick-deploy

# Create backup
make backup-create

# Deploy production with verification
make prod-deploy

# Test disaster recovery
make dr-test
```

## Environment Management

### Deploying Environments

Each environment is completely isolated with separate:

- Database instances
- Redis instances
- Storage paths
- Configuration files
- Docker networks

```powershell
# Deploy specific environments
.\scripts\ats-cli.ps1 deploy-dev
.\scripts\ats-cli.ps1 deploy-staging
.\scripts\ats-cli.ps1 deploy-prod

# Check environment status
.\scripts\ats-cli.ps1 env-status

# Stop environments
.\scripts\ats-cli.ps1 stop-dev
```

### Environment Configuration

Environment-specific settings are managed through:

- `environments/.env.dev` - Development configuration
- `environments/.env.staging` - Staging configuration
- `environments/.env.prod` - Production configuration
- `docker-compose.{env}.yml` - Docker overrides per environment

## Backup Management

### Creating Backups

```powershell
# Create backup with automatic ID
.\scripts\ats-cli.ps1 backup-create

# Create backup with custom ID
python scripts/backup_database.py create --backup-id "pre-deployment-backup"
```

### Restoring Backups

```powershell
# List available backups
.\scripts\ats-cli.ps1 backup-list

# Restore specific backup
.\scripts\ats-cli.ps1 backup-restore -BackupId "20231226_120000"

# Restore to different database
python scripts/backup_database.py restore 20231226_120000 --target-database "ats_test"
```

### Backup Verification

All backups are automatically verified by:

1. **Integrity Check** - SHA-256 checksum validation
2. **Restore Test** - Actual restore to temporary database
3. **Schema Validation** - Verify all required tables exist
4. **Data Validation** - Basic row count and structure checks

```powershell
# Check backup verification status
.\scripts\ats-cli.ps1 backup-status

# Manual verification of specific backup
python scripts/backup_database.py verify 20231226_120000
```

## Automated Scheduling

### Backup Scheduler

The backup scheduler runs continuously and handles:

- **Scheduled Backups** based on RTO configuration
- **Automatic Verification** of recent backups
- **Cleanup** of old backups based on retention policy
- **RTO Compliance Monitoring** with alerting

```powershell
# Run scheduler as daemon
python scripts/backup_scheduler.py --daemon

# Run one-time backup (for cron jobs)
python scripts/backup_scheduler.py --once
```

### Cron Configuration

For Linux/macOS production deployments:

```bash
# Production backup every 15 minutes
*/15 * * * * /path/to/venv/bin/python /path/to/scripts/backup_scheduler.py --once

# Daily cleanup at 2 AM
0 2 * * * /path/to/venv/bin/python /path/to/scripts/backup_database.py cleanup
```

## Deployment Validation

### Comprehensive Validation

The deployment validator performs:

1. **Environment Status** - All services healthy
2. **Service Health** - API, database, Redis responding
3. **RTO Compliance** - Backup/restore within time limits
4. **Security Boundaries** - Authentication properly enforced
5. **Performance** - Response times within acceptable limits
6. **Operational Readiness** - Monitoring and logging configured

```powershell
# Validate development environment
.\scripts\ats-cli.ps1 validate -Environment dev

# Get JSON output for automation
.\scripts\ats-cli.ps1 validate -Environment prod -Json
```

### Validation Report

The validator produces detailed reports:

```
================================================================================
DEPLOYMENT VALIDATION REPORT - PRODUCTION
================================================================================
Timestamp: 2023-12-26T12:00:00
Overall Status: PASSED
RTO Compliance: ✅ PASS
Security Compliance: ✅ PASS
Operational Readiness: ✅ PASS

DETAILED TEST RESULTS:
--------------------------------------------------------------------------------
Environment Status                     ✅ PASS
  └─ Environment status: healthy

Service Health                         ✅ PASS
  └─ All services healthy

Rto Compliance                         ✅ PASS
  └─ RTO compliance: backup=2.1s, restore=4.8s, max=300s

🎉 DEPLOYMENT VALIDATION PASSED - Environment is production ready!
```

## Production Deployment

### Pre-Deployment Checklist

Before production deployment:

1. ✅ All property-based tests passing
2. ✅ Security scan completed
3. ✅ Staging environment validated
4. ✅ Backup system tested
5. ✅ RTO compliance verified
6. ✅ Monitoring configured

### Production Deployment Process

```powershell
# Full production deployment with verification
.\scripts\ats-cli.ps1 prod-deploy

# This will:
# 1. Create pre-deployment backup
# 2. Deploy production environment
# 3. Run comprehensive validation
# 4. Create post-deployment backup
# 5. Verify all systems operational
```

### Rollback Procedure

If deployment fails:

```powershell
# Stop production environment
.\scripts\ats-cli.ps1 stop-prod

# Restore from pre-deployment backup
.\scripts\ats-cli.ps1 backup-restore -BackupId "pre-deployment-backup"

# Restart with previous configuration
.\scripts\ats-cli.ps1 deploy-prod
```

## Monitoring and Alerting

### Disaster Recovery Status

Monitor DR health through:

```powershell
# Get current DR status
.\scripts\ats-cli.ps1 backup-status

# Example output:
# Disaster Recovery Status:
#   Environment: production
#   Status: healthy
#   Last Backup: 2023-12-26 11:45:00
#   Time Since Backup: 14.2 minutes
#   RPO Compliance: Yes
#   Total Backups: 156
#   Verified Backups: 152
```

### Alert Conditions

The system alerts on:

- **RPO Violations** - Backup older than allowed data loss window
- **RTO Violations** - Restore taking longer than recovery time objective
- **Backup Failures** - Failed backup creation or verification
- **Verification Failures** - Backup integrity check failures

## File Structure

```
├── src/ats_backend/core/
│   ├── disaster_recovery.py      # Core DR functionality
│   └── environment_manager.py    # Environment management
├── scripts/
│   ├── backup_database.py        # Backup CLI tool
│   ├── deploy_environment.py     # Deployment CLI tool
│   ├── backup_scheduler.py       # Automated scheduler
│   ├── validate_deployment.py    # Deployment validator
│   └── ats-cli.ps1              # PowerShell CLI wrapper
├── environments/
│   ├── .env.dev                  # Development config
│   ├── .env.staging              # Staging config
│   └── .env.prod                 # Production config
├── docker-compose.{env}.yml      # Environment-specific overrides
└── backups/
    ├── dev/                      # Development backups
    ├── staging/                  # Staging backups
    └── production/               # Production backups
```

## Security Considerations

### Backup Security

- **Encryption** - Backups stored with database-level encryption
- **Access Control** - Backup files protected by filesystem permissions
- **Network Security** - Backup transfers use encrypted connections
- **Audit Trail** - All backup operations logged with actor identification

### Environment Isolation

- **Network Separation** - Each environment uses isolated Docker networks
- **Database Isolation** - Separate database instances per environment
- **Credential Isolation** - Environment-specific secrets and keys
- **Resource Isolation** - Memory and CPU limits per environment

## Troubleshooting

### Common Issues

**Backup Creation Fails**

```powershell
# Check database connectivity
python scripts/backup_database.py status

# Verify disk space
Get-WmiObject -Class Win32_LogicalDisk | Select-Object DeviceID, FreeSpace

# Check PostgreSQL service
docker-compose ps postgres
```

**Restore Takes Too Long**

```powershell
# Check RTO configuration
python scripts/backup_database.py status

# Verify backup integrity
python scripts/backup_database.py verify <backup-id>

# Check system resources
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
```

**Environment Won't Start**

```powershell
# Check service logs
docker-compose logs api
docker-compose logs postgres

# Verify configuration
.\scripts\ats-cli.ps1 env-status

# Clean up and retry
.\scripts\ats-cli.ps1 env-cleanup
.\scripts\ats-cli.ps1 deploy-dev
```

### Log Locations

- **Application Logs** - `logs/` directory
- **Docker Logs** - `docker-compose logs <service>`
- **Backup Logs** - Structured JSON logs to stdout/stderr
- **System Logs** - Windows Event Log or syslog

## Performance Tuning

### Backup Performance

- **Parallel Dumps** - Use `pg_dump` with multiple jobs
- **Compression** - Enable backup compression for large databases
- **Network Optimization** - Use local storage for backup staging
- **Incremental Backups** - Consider WAL-E or similar for large datasets

### Restore Performance

- **Parallel Restore** - Use `pg_restore` with multiple jobs
- **Memory Tuning** - Increase PostgreSQL shared_buffers during restore
- **Disk I/O** - Use SSD storage for restore operations
- **Network Bandwidth** - Ensure sufficient bandwidth for large restores

This disaster recovery system ensures the ATS Backend meets all production readiness requirements with mathematical guarantees for data protection and recovery time objectives.
