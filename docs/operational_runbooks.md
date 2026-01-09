# ATS Backend Operational Runbooks

## Table of Contents

1. [Emergency Response Procedures](#emergency-response-procedures)
2. [Service Health Monitoring](#service-health-monitoring)
3. [Performance Troubleshooting](#performance-troubleshooting)
4. [Database Issues](#database-issues)
5. [Queue Management](#queue-management)
6. [Security Incident Response](#security-incident-response)
7. [Backup and Recovery](#backup-and-recovery)
8. [Deployment Procedures](#deployment-procedures)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Emergency Response Procedures

### Critical System Down (All Services Unavailable)

**Symptoms:**

- Health check endpoints returning 5xx errors
- No response from API endpoints
- Grafana dashboards showing all services down

**Immediate Actions (< 5 minutes):**

1. Check system status: `make env-status`
2. Verify infrastructure: `docker ps -a`
3. Check system resources: `htop` or `top`
4. Review recent logs: `docker logs ats-api-prod --tail 100`

**Recovery Steps:**

1. **Quick restart attempt:**

   ```bash
   make stop-prod
   make deploy-prod
   ```

2. **If restart fails, check disk space:**

   ```bash
   df -h
   # If disk full, clean up logs and temporary files
   docker system prune -f
   ```

3. **Database recovery if needed:**

   ```bash
   # Check database status
   docker logs ats-postgres-prod --tail 50

   # If database corrupted, restore from backup
   python scripts/backup_database.py restore <latest_backup_id>
   ```

4. **Escalation:** If not resolved in 15 minutes, contact senior engineer

### High Error Rate (>5% API errors)

**Symptoms:**

- Prometheus alert: `HighAPIErrorRate`
- Grafana showing spike in 5xx responses
- User reports of application failures

**Investigation Steps:**

1. **Check error patterns:**

   ```bash
   # View recent API logs
   docker logs ats-api-prod --tail 200 | grep ERROR

   # Check specific error types
   curl http://localhost:8002/monitoring/diagnostic
   ```

2. **Identify root cause:**

   - Database connection issues
   - External service failures
   - Memory/CPU exhaustion
   - Code deployment issues

3. **Mitigation:**
   - Scale workers if queue backup: `docker-compose up --scale worker=8`
   - Restart services if memory leak suspected
   - Rollback deployment if recent change

### Queue Backup (>500 tasks)

**Symptoms:**

- Prometheus alert: `CriticalQueueDepth`
- Slow resume processing
- User complaints about delays

**Immediate Actions:**

1. **Scale workers:**

   ```bash
   docker-compose -f docker-compose.prod.yml up --scale worker=8 -d
   ```

2. **Check worker health:**

   ```bash
   # Monitor worker status
   python scripts/check-worker-health.py

   # View worker logs
   docker logs ats-worker-prod-1 --tail 100
   ```

3. **Clear stuck tasks if needed:**
   ```bash
   python scripts/manage_tasks.py clear-stuck
   ```

---

## Service Health Monitoring

### Health Check Endpoints

**Primary Health Check:**

```bash
curl http://localhost:8002/monitoring/health
```

**Simple Status Check:**

```bash
curl http://localhost:8002/monitoring/health/simple
```

**Kubernetes Probes:**

```bash
# Readiness probe
curl http://localhost:8002/monitoring/readiness

# Liveness probe
curl http://localhost:8002/monitoring/liveness
```

### Monitoring Dashboard Access

**Grafana:** http://localhost:3000

- Username: admin
- Password: ${GRAFANA_ADMIN_PASSWORD}

**Prometheus:** http://localhost:9090

**Alertmanager:** http://localhost:9093

### Key Metrics to Monitor

1. **API Performance:**

   - Response time P95 < 2 seconds
   - Error rate < 5%
   - Throughput trends

2. **Queue Health:**

   - Queue depth < 100 (warning), < 500 (critical)
   - Worker count > 1
   - Task processing rate

3. **System Resources:**

   - CPU usage < 90%
   - Memory usage < 90%
   - Disk usage < 95%

4. **Database:**
   - Connection pool utilization
   - Query performance
   - Lock contention

---

## Performance Troubleshooting

### Slow API Response Times

**Investigation:**

1. **Check current performance:**

   ```bash
   curl http://localhost:8002/monitoring/diagnostic | jq '.performance_summary'
   ```

2. **Identify bottlenecks:**

   - Database query performance
   - External service calls
   - CPU/Memory constraints
   - Network latency

3. **Database optimization:**

   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;

   -- Check active connections
   SELECT count(*) FROM pg_stat_activity;
   ```

**Solutions:**

- Add database indexes for slow queries
- Optimize N+1 query patterns
- Implement caching for frequent queries
- Scale database resources

### High Memory Usage

**Investigation:**

1. **Check memory usage by service:**

   ```bash
   docker stats --no-stream
   ```

2. **Identify memory leaks:**
   ```bash
   # Monitor memory trends
   curl http://localhost:8002/monitoring/trends?hours=6
   ```

**Solutions:**

- Restart services with memory leaks
- Optimize data structures and caching
- Increase memory limits if needed
- Review recent code changes

### Resume Processing Slowdown

**Investigation:**

1. **Check OCR fallback rate:**

   ```bash
   curl http://localhost:8002/monitoring/metrics | grep ocr_fallback
   ```

2. **Review processing times:**
   ```bash
   curl http://localhost:8002/monitoring/diagnostic | jq '.performance_summary.resume_parsing'
   ```

**Solutions:**

- Scale resume processing workers
- Optimize OCR processing pipeline
- Check for corrupted resume files
- Review text extraction algorithms

---

## Database Issues

### Connection Pool Exhaustion

**Symptoms:**

- "connection pool exhausted" errors
- Slow database queries
- API timeouts

**Investigation:**

```sql
-- Check active connections
SELECT
    state,
    count(*)
FROM pg_stat_activity
GROUP BY state;

-- Check long-running queries
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
```

**Solutions:**

1. Kill long-running queries:

   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <pid>;
   ```

2. Increase connection pool size in configuration

3. Optimize application connection usage

### Database Performance Issues

**Investigation:**

```sql
-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public';
```

**Solutions:**

- Add missing indexes
- Update table statistics: `ANALYZE;`
- Consider partitioning large tables
- Vacuum and reindex: `VACUUM ANALYZE;`

---

## Queue Management

### Celery Worker Management

**Check worker status:**

```bash
python scripts/check-worker-health.py
```

**Scale workers:**

```bash
# Scale up
docker-compose -f docker-compose.prod.yml up --scale worker=8 -d

# Scale down
docker-compose -f docker-compose.prod.yml up --scale worker=2 -d
```

**Clear stuck tasks:**

```bash
python scripts/manage_tasks.py clear-stuck
python scripts/manage_tasks.py purge-failed
```

### Queue Monitoring

**Check queue depths:**

```bash
curl http://localhost:8002/monitoring/diagnostic | jq '.queue_status'
```

**Monitor task processing:**

```bash
# View worker logs
docker logs ats-worker-prod-1 --follow

# Check task statistics
python scripts/manage_tasks.py stats
```

---

## Security Incident Response

### Suspected RLS Bypass

**Immediate Actions:**

1. **Check alerts:**

   ```bash
   curl http://localhost:8002/monitoring/alerts | jq '.active_alerts[] | select(.name | contains("rls"))'
   ```

2. **Review security logs:**

   ```bash
   docker logs ats-api-prod | grep "RLS_BYPASS"
   ```

3. **Isolate affected client:**
   ```sql
   -- Temporarily disable client access
   UPDATE clients SET is_active = false WHERE id = '<client_id>';
   ```

### High Authentication Failures

**Investigation:**

1. **Check failure patterns:**

   ```bash
   curl http://localhost:8002/monitoring/metrics | grep auth_failures
   ```

2. **Review source IPs:**
   ```bash
   docker logs ats-api-prod | grep "Login failed" | awk '{print $NF}' | sort | uniq -c | sort -nr
   ```

**Mitigation:**

- Block suspicious IPs at firewall level
- Implement additional rate limiting
- Enable account lockout mechanisms
- Contact affected users if legitimate accounts compromised

---

## Backup and Recovery

### Create Manual Backup

```bash
# Create immediate backup
python scripts/backup_database.py create

# List available backups
python scripts/backup_database.py list

# Check backup status
python scripts/backup_database.py status
```

### Restore from Backup

```bash
# Restore specific backup
python scripts/backup_database.py restore <backup_id>

# Restore latest backup
python scripts/backup_database.py restore latest
```

### Disaster Recovery Testing

```bash
# Test full disaster recovery
make dr-test

# Validate backup integrity
python scripts/backup_database.py verify <backup_id>
```

---

## Deployment Procedures

### Production Deployment

```bash
# Full production deployment
make prod-deploy

# Deploy with validation
python scripts/deploy_environment.py deploy prod
python scripts/validate_deployment.py prod
```

### Rollback Procedures

```bash
# Quick rollback to previous version
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# Database rollback (if needed)
python scripts/backup_database.py restore <previous_backup_id>
```

### Blue-Green Deployment

```bash
# Deploy to staging first
make deploy-staging
python scripts/validate_deployment.py staging

# If validation passes, deploy to production
make deploy-prod
```

---

## Monitoring and Alerting

### Alert Configuration

**Critical Alerts (Immediate Response):**

- Service down
- High error rate (>5%)
- No workers available
- RLS bypass attempt
- Critical queue depth (>500)

**Warning Alerts (Response within 1 hour):**

- High response time
- High resource usage
- Queue backup (>100)
- OCR fallback rate high

### Alert Response Procedures

1. **Acknowledge alert** in Alertmanager
2. **Investigate** using runbook procedures
3. **Mitigate** immediate impact
4. **Document** findings and actions taken
5. **Follow up** with root cause analysis

### Custom Metrics

**Add custom metrics:**

```python
from ats_backend.core.observability import observability_system

# Track custom operation
await observability_system.track_operation(
    operation="custom_operation",
    duration_seconds=1.5,
    success=True,
    metadata={"key": "value"}
)
```

---

## Common Issues and Solutions

### Issue: "Database connection refused"

**Cause:** Database service not running or network issues

**Solution:**

```bash
# Check database status
docker logs ats-postgres-prod

# Restart database
docker-compose -f docker-compose.prod.yml restart postgres

# Check network connectivity
docker network ls
docker network inspect ats-backend_default
```

### Issue: "Redis connection timeout"

**Cause:** Redis service overloaded or not responding

**Solution:**

```bash
# Check Redis status
docker logs ats-redis-prod

# Check Redis memory usage
docker exec ats-redis-prod redis-cli info memory

# Restart Redis if needed
docker-compose -f docker-compose.prod.yml restart redis
```

### Issue: "High CPU usage"

**Cause:** Resource-intensive operations or inefficient code

**Solution:**

```bash
# Identify CPU-intensive processes
docker exec ats-api-prod top

# Check for infinite loops or inefficient queries
docker logs ats-api-prod | grep "slow query"

# Scale resources if needed
docker-compose -f docker-compose.prod.yml up --scale api=2 -d
```

### Issue: "Disk space full"

**Cause:** Log files, temporary files, or database growth

**Solution:**

```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -f

# Rotate logs
docker logs ats-api-prod > /dev/null

# Clean up old backups
python scripts/backup_database.py cleanup
```

---

## Emergency Contacts

**On-Call Engineer:** [Contact Information]
**Database Administrator:** [Contact Information]
**Security Team:** [Contact Information]
**Infrastructure Team:** [Contact Information]

## Escalation Matrix

1. **Level 1:** On-call engineer (0-15 minutes)
2. **Level 2:** Senior engineer (15-30 minutes)
3. **Level 3:** Engineering manager (30-60 minutes)
4. **Level 4:** CTO/VP Engineering (>60 minutes)

---

_Last Updated: [Current Date]_
_Version: 1.0_
