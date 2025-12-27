# ATS Backend Makefile

.PHONY: help install test test-unit test-property test-integration test-all lint format clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -e ".[dev]"

test: test-property ## Run property-based tests (default)

test-unit: ## Run unit tests only
	pytest tests/ -m "unit" -v

test-property: ## Run property-based tests only
	HYPOTHESIS_PROFILE=production_hardening pytest tests/property_based/ -m "property_test" -v

test-property-dev: ## Run property-based tests in development mode (more examples)
	HYPOTHESIS_PROFILE=dev pytest tests/property_based/ -m "property_test" -v

test-property-ci: ## Run property-based tests in CI mode (deterministic)
	CI=1 HYPOTHESIS_PROFILE=ci pytest tests/property_based/ -m "property_test" -v --tb=short

test-integration: ## Run integration tests only
	pytest tests/ -m "integration" -v

test-all: ## Run all tests
	pytest tests/ -v

test-coverage: ## Run tests with coverage report
	pytest tests/ --cov=src/ats_backend --cov-report=html --cov-report=term

lint: ## Run linting
	flake8 src/ tests/
	mypy src/

format: ## Format code
	black src/ tests/
	isort src/ tests/

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/
	rm -rf tests/property_based/.hypothesis_examples/

# Development commands
dev-setup: install ## Set up development environment
	@echo "Development environment setup complete"

dev-test: ## Run tests in development mode
	HYPOTHESIS_PROFILE=dev pytest tests/property_based/ -v -s

# CI commands
ci-test: test-property-ci test-unit ## Run tests in CI mode

# Property-based testing specific commands
pbt-demo: ## Run property-based testing framework demo
	HYPOTHESIS_PROFILE=production_hardening pytest tests/property_based/test_framework_demo.py -v

pbt-verbose: ## Run property-based tests with verbose output
	HYPOTHESIS_PROFILE=production_hardening pytest tests/property_based/ -v -s --hypothesis-show-statistics

pbt-profile: ## Profile property-based test performance
	HYPOTHESIS_PROFILE=dev pytest tests/property_based/ --profile-svg

# Environment Management Commands
deploy-dev: ## Deploy development environment
	python scripts/deploy_environment.py deploy dev

deploy-staging: ## Deploy staging environment
	python scripts/deploy_environment.py deploy staging

deploy-prod: ## Deploy production environment
	python scripts/deploy_environment.py deploy prod --force

stop-dev: ## Stop development environment
	python scripts/deploy_environment.py stop dev

stop-staging: ## Stop staging environment
	python scripts/deploy_environment.py stop staging

stop-prod: ## Stop production environment
	python scripts/deploy_environment.py stop prod

env-status: ## Show status of all environments
	python scripts/deploy_environment.py status

env-cleanup: ## Clean up all environments
	python scripts/deploy_environment.py cleanup

# Disaster Recovery Commands
backup-create: ## Create database backup
	python scripts/backup_database.py create

backup-restore: ## Restore from backup (usage: make backup-restore BACKUP_ID=<id>)
	python scripts/backup_database.py restore $(BACKUP_ID)

backup-list: ## List available backups
	python scripts/backup_database.py list

backup-cleanup: ## Clean up old backups
	python scripts/backup_database.py cleanup

backup-status: ## Show disaster recovery status
	python scripts/backup_database.py status

# One-command deployment (15 minutes or less)
quick-deploy: ## Deploy complete development environment in under 15 minutes
	@echo "🚀 Starting quick deployment..."
	@echo "⏱️  Target: Complete deployment in under 15 minutes"
	make env-cleanup
	make deploy-dev
	make backup-create
	@echo "✅ Quick deployment completed!"

# Production deployment with full verification
prod-deploy: ## Deploy production environment with full verification
	@echo "🚀 Starting production deployment..."
	@echo "⚠️  This will deploy to production - ensure you have proper authorization"
	@read -p "Continue with production deployment? [y/N] " confirm && [ "$$confirm" = "y" ]
	make backup-create
	make deploy-prod
	make backup-create
	@echo "✅ Production deployment completed!"

# Disaster recovery testing
dr-test: ## Test disaster recovery procedures
	@echo "🧪 Testing disaster recovery procedures..."
	make backup-create
	make backup-list
	make backup-status
	@echo "✅ Disaster recovery test completed!"
# Health check commands
health-check: ## Run comprehensive health check for production
	python scripts/health_check.py --environment prod

health-check-dev: ## Run health check for development environment
	python scripts/health_check.py --environment dev

health-check-staging: ## Run health check for staging environment
	python scripts/health_check.py --environment staging

health-check-json: ## Run health check and output JSON
	python scripts/health_check.py --environment prod --json

health-check-quiet: ## Run health check and only show critical issues
	python scripts/health_check.py --environment prod --quiet

# Monitoring commands
monitoring-start: ## Start monitoring stack (Prometheus, Grafana, Alertmanager)
	docker-compose -f docker-compose.prod.yml up -d prometheus grafana alertmanager node-exporter postgres-exporter redis-exporter loki promtail

monitoring-stop: ## Stop monitoring stack
	docker-compose -f docker-compose.prod.yml stop prometheus grafana alertmanager node-exporter postgres-exporter redis-exporter loki promtail

monitoring-restart: ## Restart monitoring stack
	make monitoring-stop
	make monitoring-start

monitoring-logs: ## View monitoring stack logs
	docker-compose -f docker-compose.prod.yml logs -f prometheus grafana alertmanager

# Alert management
alerts-list: ## List active alerts
	curl -s http://localhost:8002/monitoring/alerts | jq '.active_alerts'

alerts-clear: ## Clear all alerts (usage: make alerts-clear ALERT_NAME=<name>)
	curl -X POST http://localhost:8002/monitoring/alerts/$(ALERT_NAME)/clear

# Metrics and diagnostics
metrics: ## Get current metrics
	curl -s http://localhost:8002/monitoring/metrics

diagnostic: ## Get 60-second diagnostic
	curl -s http://localhost:8002/monitoring/diagnostic | jq '.'

trends: ## Get performance trends (usage: make trends HOURS=24)
	curl -s "http://localhost:8002/monitoring/trends?hours=$(or $(HOURS),24)" | jq '.'

# Production monitoring dashboard URLs
dashboard-urls: ## Show monitoring dashboard URLs
	@echo "📊 Monitoring Dashboard URLs:"
	@echo "  Grafana:      http://localhost:3000"
	@echo "  Prometheus:   http://localhost:9090"
	@echo "  Alertmanager: http://localhost:9093"
	@echo ""
	@echo "🔍 API Monitoring Endpoints:"
	@echo "  Health:       http://localhost:8002/monitoring/health"
	@echo "  Metrics:      http://localhost:8002/monitoring/metrics"
	@echo "  Diagnostic:   http://localhost:8002/monitoring/diagnostic"
	@echo "  Alerts:       http://localhost:8002/monitoring/alerts"

# Update production deployment to include health check
prod-deploy-verified: ## Deploy production with health verification
	@echo "🚀 Starting verified production deployment..."
	@echo "⚠️  This will deploy to production - ensure you have proper authorization"
	@read -p "Continue with production deployment? [y/N] " confirm && [ "$confirm" = "y" ]
	make backup-create
	make deploy-prod
	make monitoring-start
	sleep 30
	make health-check
	make backup-create
	@echo "✅ Verified production deployment completed!"

# Advanced deployment orchestration
deploy-advanced: ## Deploy with comprehensive validation and monitoring
	python scripts/deployment_orchestrator.py deploy $(ENV)

deploy-zero-downtime: ## Zero-downtime deployment (staging -> prod)
	python scripts/deployment_orchestrator.py zero-downtime prod

deploy-dev-full: ## Full development deployment with all features
	python scripts/deployment_orchestrator.py deploy dev

deploy-staging-full: ## Full staging deployment with validation
	python scripts/deployment_orchestrator.py deploy staging

deploy-prod-full: ## Full production deployment with all safeguards
	python scripts/deployment_orchestrator.py deploy prod

# Quick deployment shortcuts
quick-dev: ## Quick development deployment (no monitoring/backups)
	python scripts/deployment_orchestrator.py deploy dev --no-monitoring --no-backup

quick-staging: ## Quick staging deployment (no backups)
	python scripts/deployment_orchestrator.py deploy staging --no-backup

# Infrastructure validation
validate-infrastructure: ## Validate all infrastructure components
	@echo "🔍 Validating infrastructure..."
	python scripts/validate_deployment.py dev
	python scripts/validate_deployment.py staging
	python scripts/validate_deployment.py prod
	@echo "✅ Infrastructure validation completed!"

# Complete environment lifecycle
lifecycle-test: ## Test complete environment lifecycle
	@echo "🧪 Testing complete environment lifecycle..."
	make env-cleanup
	make deploy-dev-full
	make deploy-staging-full
	make validate-infrastructure
	make dr-test
	@echo "✅ Lifecycle test completed!"