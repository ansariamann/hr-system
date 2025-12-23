#!/bin/bash

# Development shutdown script for ATS Backend

set -e

echo "Stopping ATS Backend Development Environment..."

# Stop all services
docker-compose down

echo "Development environment stopped!"