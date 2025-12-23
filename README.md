# ATS Backend System

A multi-tenant Applicant Tracking System (ATS) backend that automates resume processing through email ingestion, intelligent parsing, and secure data management.

## Features

- **Multi-tenant Architecture**: Strict data isolation using PostgreSQL Row-Level Security (RLS)
- **Email Ingestion**: Automated resume processing from email attachments
- **Intelligent Parsing**: PDF text extraction with OCR support for scanned documents
- **Background Processing**: Celery workers for CPU-intensive tasks
- **Duplicate Detection**: Fuzzy matching to prevent rehiring candidates with "LEFT" status
- **RESTful API**: FastAPI-based endpoints for candidate and application management
- **Containerized Deployment**: Docker Compose for easy deployment and scaling

## Architecture

The system consists of the following components:

- **FastAPI Web Service**: REST API endpoints and authentication
- **Celery Workers**: Background resume processing and parsing
- **PostgreSQL**: Multi-tenant data storage with RLS policies
- **Redis**: Task queue management and caching
- **OCR Engine**: Tesseract for image-to-text conversion

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Development Setup

1. **Clone and setup environment**:

   ```bash
   git clone <repository-url>
   cd ats-backend
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start development services**:

   ```bash
   chmod +x scripts/start-dev.sh
   ./scripts/start-dev.sh
   ```

3. **Install Python dependencies** (for local development):

   ```bash
   pip install -e .[dev]
   ```

4. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

### Production Deployment

1. **Build and start all services**:

   ```bash
   docker-compose up -d
   ```

2. **Check service health**:
   ```bash
   docker-compose ps
   curl http://localhost:8000/health
   ```

## Configuration

Key environment variables (see `.env.example` for full list):

- `POSTGRES_*`: Database configuration
- `REDIS_*`: Redis configuration
- `SECRET_KEY`: JWT secret key (change in production!)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `ENVIRONMENT`: Environment name (development, staging, production)

## API Documentation

Once running, visit:

- API Documentation: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ats_backend

# Run property-based tests
pytest -m property
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/
mypy src/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Monitoring

- **Celery Flower**: http://localhost:5555 (development profile)
- **Application Logs**: `docker-compose logs -f api worker`
- **Database Logs**: `docker-compose logs -f postgres`

## Security

- Multi-tenant data isolation via PostgreSQL RLS
- JWT-based authentication
- Environment-based secrets management
- Input validation and sanitization
- Audit logging for all data modifications

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details.
