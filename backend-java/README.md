# ATS Backend — Java 21 / Spring Boot 3

> Migrated from Python (FastAPI + SQLAlchemy + Celery) to **Java 21 + Spring Boot 3.3**.

## Stack

| Layer | Technology |
|---|---|
| Language | Java 21 (Virtual Threads / Project Loom) |
| Framework | Spring Boot 3.3 (Web, Data JPA, Security) |
| Database | PostgreSQL + Flyway migrations |
| Multi-tenancy | PostgreSQL RLS via HikariCP + TenantContext ThreadLocal |
| Auth | Spring Security 6 + JJWT (HS256) — BCrypt compatible with Python passlib |
| Background Jobs | JobRunr (replaces Celery) |
| PDF / OCR | Apache PDFBox 3 + Tess4J (replaces PyPDF2 + pytesseract) |
| Fuzzy Matching | Apache commons-text (Levenshtein + Jaro-Winkler) |
| Realtime | Spring SseEmitter + heartbeats (replaces FastAPI SSE) |
| API Docs | SpringDoc OpenAPI → `/swagger-ui.html` |

## Getting Started

### Prerequisites
- Java 21 (Temurin or GraalVM)
- Maven 3.9+
- PostgreSQL 15+
- (Optional) Tesseract 5 + `eng.traineddata` for scanned PDF OCR

### Setup

```bash
# 1. Copy env and fill in database credentials
cp .env.example .env

# 2. Create DB
createdb ats_db

# 3. Build
mvn clean package -DskipTests

# 4. Run (Flyway runs migrations automatically on startup)
mvn spring-boot:run
```

### API Documentation
- Swagger UI: http://localhost:8080/swagger-ui.html
- OpenAPI JSON: http://localhost:8080/api-docs
- JobRunr Dashboard: http://localhost:8000

## Project Structure

```
backend-java/
├── pom.xml
└── src/main/
    ├── java/com/ats/
    │   ├── AtsBackendApplication.java       # Entry point
    │   ├── config/                          # DataSource, TenantContext, OpenAPI
    │   ├── domain/
    │   │   ├── entity/                      # JPA entities (Client, Candidate, Application…)
    │   │   ├── repository/                  # Spring Data repositories
    │   │   └── enums/                       # ApplicationStatus, CandidateStatus, UserRole
    │   ├── service/                         # Business logic + FSM service
    │   ├── api/controller/                  # REST controllers
    │   ├── security/                        # Spring Security config + JWT filter
    │   ├── resume/                          # PDF extraction (PDFBox + Tess4J)
    │   ├── worker/                          # JobRunr background workers
    │   ├── sse/                             # Server-Sent Events controller
    │   └── exception/                       # Global exception handler
    └── resources/
        ├── application.yml
        └── db/migration/
            └── V1__initial_schema.sql       # Flyway baseline (consolidates all 33 Alembic scripts)
```

## Frontend Integration (Phase 4)

Update `VITE_API_URL` in both frontend apps to point to this service:

```
frontend/hr-dashboard/.env   → VITE_API_URL=http://localhost:8080
frontend/client-portal/.env  → VITE_API_URL=http://localhost:8080
```

All API paths are preserved: `/api/v1/auth/*`, `/api/v1/candidates/*`, `/api/v1/applications/*`, etc.

## Migration Branch

`feature/java-spring-migration` — off `master`.
