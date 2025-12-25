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