# ATS Backend Troubleshooting Guide

## Quick Diagnostic Commands

### System Status Check

```bash
# Overall system health
curl http://localhost:8002/monitoring/health/simple

# Detailed diagnostic (60-second capability)
curl http://localhost:8002/monitoring/diagnostic | jq '.'

# Environment status
make env-status

# Active alerts
curl http://localhost:8002/monitoring/alerts | jq '.active_alerts'
```

### Service Status

```bash
# Docker services
docker ps -a

# Service logs
docker logs ats-api-prod --tail 100
docker logs ats-postgres-prod --tail 50
docker logs ats-redis-prod --tail 50
docker logs ats-worker-prod-1 --tail 100
```

### Performance Metrics

```bash
# Current performance
curl http://localhost:8002/monitoring/metrics | grep -E "(response_time|error_rate|queue_depth)"

# Resource usage
docker stats --no-stream

# System resources
htop
```

---

## Problem Categories

## 1. API Performance Issues

### Symptom: Slow Response Times (>2 seconds)

**Quick Diagnosis:**

```bash
# Check current P95 response time
curl http://localhost:8002/monitoring/diagnostic | jq '.performance_summary'

# Check for database bottlenecks
docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 5;"
```

**Common Causes & Solutions:**

1. **Database Query Performance**

   ```bash
   # Check slow queries
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '1 minute';"

   # Solution: Kill long-running queries
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
   SELECT pg_terminate_backend(<pid>);"
   ```

2. **High CPU Usage**

   ```bash
   # Check CPU usage by container
   docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

   # Solution: Scale API instances
   docker-compose -f docker-compose.prod.yml up --scale api=2 -d
   ```

3. **Memory Pressure**

   ```bash
   # Check memory usage
   free -h
   docker exec ats-api-prod cat /proc/meminfo | grep -E "(MemTotal|MemAvailable)"

   # Solution: Restart services to clear memory leaks
   docker-compose -f docker-compose.prod.yml restart api
   ```

### Symptom: High Error Rate (>5%)

**Quick Diagnosis:**

```bash
# Check error patterns
docker logs ats-api-prod --tail 200 | grep -E "(ERROR|CRITICAL)" | tail -10

# Check error rate by endpoint
curl http://localhost:8002/monitoring/metrics | grep http_requests_total
```

**Common Causes & Solutions:**

1. **Database Connection Issues**

   ```bash
   # Check connection pool
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
   SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"

   # Solution: Restart database if connection pool exhausted
   docker-compose -f docker-compose.prod.yml restart postgres
   ```

2. **External Service Failures**

   ```bash
   # Check external service connectivity
   docker exec ats-api-prod curl -I https://external-service.com/health

   # Solution: Implement circuit breaker or retry logic
   ```

3. **Code Deployment Issues**

   ```bash
   # Check recent deployments
   docker images | grep ats-backend

   # Solution: Rollback to previous version
   docker-compose -f docker-compose.prod.yml down
   docker-compose -f docker-compose.prod.yml up -d
   ```

---

## 2. Queue and Worker Issues

### Symptom: Queue Backup (>100 tasks)

**Quick Diagnosis:**

```bash
# Check queue depths
curl http://localhost:8002/monitoring/diagnostic | jq '.queue_status'

# Check worker status
python scripts/check-worker-health.py

# Check worker logs for errors
docker logs ats-worker-prod-1 --tail 50 | grep ERROR
```

**Common Causes & Solutions:**

1. **Insufficient Workers**

   ```bash
   # Check current worker count
   docker ps | grep worker

   # Solution: Scale workers
   docker-compose -f docker-compose.prod.yml up --scale worker=8 -d
   ```

2. **Worker Crashes**

   ```bash
   # Check for crashed workers
   docker ps -a | grep worker | grep Exited

   # Solution: Restart crashed workers
   docker-compose -f docker-compose.prod.yml up -d worker
   ```

3. **Stuck Tasks**

   ```bash
   # Check for long-running tasks
   python scripts/manage-tasks.py list-active

   # Solution: Clear stuck tasks
   python scripts/manage-tasks.py clear-stuck
   ```

### Symptom: Resume Processing Failures

**Quick Diagnosis:**

```bash
# Check OCR fallback rate
curl http://localhost:8002/monitoring/metrics | grep ocr_fallback

# Check resume processing errors
docker logs ats-worker-prod-1 | grep "resume.*error" | tail -10
```

**Common Causes & Solutions:**

1. **OCR Service Issues**

   ```bash
   # Test OCR functionality
   docker exec ats-worker-prod-1 tesseract --version

   # Solution: Restart workers or update OCR dependencies
   docker-compose -f docker-compose.prod.yml restart worker
   ```

2. **File Storage Issues**

   ```bash
   # Check storage space
   df -h /app/storage

   # Check file permissions
   docker exec ats-api-prod ls -la /app/storage/

   # Solution: Clean up old files or fix permissions
   docker exec ats-api-prod find /app/storage -type f -mtime +30 -delete
   ```

---

## 3. Database Issues

### Symptom: Database Connection Failures

**Quick Diagnosis:**

```bash
# Check database status
docker logs ats-postgres-prod --tail 20

# Test database connectivity
docker exec ats-postgres-prod pg_isready -U ats_production_user

# Check database processes
docker exec ats-postgres-prod ps aux | grep postgres
```

**Common Causes & Solutions:**

1. **Database Not Running**

   ```bash
   # Check if database container is running
   docker ps | grep postgres

   # Solution: Start database
   docker-compose -f docker-compose.prod.yml up -d postgres
   ```

2. **Connection Pool Exhaustion**

   ```bash
   # Check active connections
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
   SELECT count(*) as active_connections FROM pg_stat_activity;"

   # Solution: Kill idle connections
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE state = 'idle' AND state_change < now() - interval '1 hour';"
   ```

3. **Disk Space Issues**

   ```bash
   # Check database disk usage
   docker exec ats-postgres-prod df -h

   # Solution: Clean up old data or expand storage
   docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "VACUUM FULL;"
   ```

### Symptom: Slow Database Queries

**Quick Diagnosis:**

```bash
# Check slow queries
docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# Check database locks
docker exec ats-postgres-prod psql -U ats_production_user -d ats_production -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;"
```

**Solutions:**

1. **Add Missing Indexes**

   ```sql
   -- Identify missing indexes
   SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE schemaname = 'public' AND n_distinct > 100;

   -- Create indexes for frequently queried columns
   CREATE INDEX CONCURRENTLY idx_candidates_email ON candidates(email);
   ```

2. **Optimize Queries**

   ```sql
   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM candidates WHERE email = 'test@example.com';

   -- Update table statistics
   ANALYZE candidates;
   ```

---

## 4. Redis Issues

### Symptom: Redis Connection Timeouts

**Quick Diagnosis:**

```bash
# Check Redis status
docker logs ats-redis-prod --tail 20

# Test Redis connectivity
docker exec ats-redis-prod redis-cli ping

# Check Redis memory usage
docker exec ats-redis-prod redis-cli info memory
```

**Common Causes & Solutions:**

1. **Redis Memory Issues**

   ```bash
   # Check memory usage
   docker exec ats-redis-prod redis-cli info memory | grep used_memory_human

   # Solution: Clear cache or increase memory
   docker exec ats-redis-prod redis-cli FLUSHDB
   ```

2. **Redis Performance Issues**

   ```bash
   # Check slow log
   docker exec ats-redis-prod redis-cli SLOWLOG GET 10

   # Solution: Optimize Redis operations or increase resources
   ```

---

## 5. Security Issues

### Symptom: High Authentication Failures

**Quick Diagnosis:**

```bash
# Check authentication failure rate
curl http://localhost:8002/monitoring/metrics | grep auth_failures

# Check recent failed login attempts
docker logs ats-api-prod | grep "Login failed" | tail -20

# Check source IPs
docker logs ats-api-prod | grep "Login failed" | awk '{print $NF}' | sort | uniq -c | sort -nr
```

**Solutions:**

1. **Block Suspicious IPs**

   ```bash
   # Add firewall rule
   iptables -A INPUT -s <suspicious_ip> -j DROP

   # Or use fail2ban for automatic blocking
   ```

2. **Enable Account Lockout**
   ```bash
   # Check lockout configuration
   curl http://localhost:8002/monitoring/alert-rules | jq '.alert_rules[] | select(.name | contains("auth"))'
   ```

### Symptom: RLS Bypass Attempts

**Quick Diagnosis:**

```bash
# Check for RLS bypass alerts
curl http://localhost:8002/monitoring/alerts | jq '.active_alerts[] | select(.name | contains("rls"))'

# Check security logs
docker logs ats-api-prod | grep "RLS_BYPASS" | tail -10
```

**Immediate Actions:**

1. **Isolate Affected Client**

   ```sql
   -- Temporarily disable client
   UPDATE clients SET is_active = false WHERE id = '<client_id>';
   ```

2. **Review Security Logs**
   ```bash
   # Export security events for analysis
   docker logs ats-api-prod | grep -E "(RLS_BYPASS|SECURITY)" > security_incident.log
   ```

---

## 6. Monitoring and Alerting Issues

### Symptom: Missing Metrics

**Quick Diagnosis:**

```bash
# Check metrics endpoint
curl http://localhost:8002/monitoring/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Grafana data sources
curl -u admin:${GRAFANA_ADMIN_PASSWORD} http://localhost:3000/api/datasources
```

**Solutions:**

1. **Restart Monitoring Stack**

   ```bash
   docker-compose -f docker-compose.prod.yml restart prometheus grafana
   ```

2. **Check Configuration**
   ```bash
   # Validate Prometheus config
   docker exec ats-prometheus-prod promtool check config /etc/prometheus/prometheus.yml
   ```

### Symptom: Alerts Not Firing

**Quick Diagnosis:**

```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Check Alertmanager status
curl http://localhost:9093/api/v1/status

# Test alert rule
curl -X POST http://localhost:9093/api/v1/alerts
```

---

## 7. Backup and Recovery Issues

### Symptom: Backup Failures

**Quick Diagnosis:**

```bash
# Check backup status
python scripts/backup_database.py status

# Check recent backup logs
docker logs ats-postgres-prod | grep backup

# Test backup creation
python scripts/backup_database.py create --test
```

**Solutions:**

1. **Fix Storage Issues**

   ```bash
   # Check backup storage space
   df -h /app/backups

   # Clean up old backups
   python scripts/backup_database.py cleanup
   ```

2. **Fix Permissions**

   ```bash
   # Check backup directory permissions
   ls -la /app/backups/

   # Fix permissions if needed
   chmod 755 /app/backups/
   ```

---

## Emergency Procedures

### Complete System Recovery

1. **Stop all services:**

   ```bash
   make stop-prod
   ```

2. **Restore from backup:**

   ```bash
   python scripts/backup_database.py restore latest
   ```

3. **Start services:**

   ```bash
   make deploy-prod
   ```

4. **Validate recovery:**
   ```bash
   python scripts/validate_deployment.py prod
   ```

### Data Corruption Recovery

1. **Identify corruption scope:**

   ```sql
   -- Check table integrity
   SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
   FROM pg_stat_user_tables
   ORDER BY n_tup_ins DESC;
   ```

2. **Restore affected tables:**
   ```bash
   # Restore specific tables from backup
   python scripts/backup_database.py restore-table <backup_id> <table_name>
   ```

---

## Performance Optimization

### Database Optimization

```sql
-- Update statistics
ANALYZE;

-- Reindex tables
REINDEX DATABASE ats_production;

-- Check for bloated tables
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
       pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Application Optimization

```bash
# Profile API performance
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8002/api/candidates

# Monitor memory usage
docker exec ats-api-prod cat /proc/meminfo | grep -E "(MemTotal|MemAvailable|MemFree)"

# Check for memory leaks
docker stats --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}" --no-stream
```

---

## Preventive Maintenance

### Daily Checks

- [ ] Review monitoring dashboards
- [ ] Check alert status
- [ ] Verify backup completion
- [ ] Monitor resource usage trends

### Weekly Checks

- [ ] Review performance trends
- [ ] Update security patches
- [ ] Clean up old logs and backups
- [ ] Test disaster recovery procedures

### Monthly Checks

- [ ] Capacity planning review
- [ ] Security audit
- [ ] Performance optimization
- [ ] Documentation updates

---

_Last Updated: [Current Date]_
_Version: 1.0_
