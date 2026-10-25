# Enterprise ATS (Applicant Tracking System)
### Modern Architecture: Java 21 / Spring Boot 3 + React

A high-performance, multi-tenant Applicant Tracking System (ATS) featuring automated resume parsing, duplicate candidate detection, PostgreSQL Row-Level Security (RLS), and a unified React single-page frontend.

---

## 🚀 Technology Stack

- **Backend**: Java 21 (LTS), Spring Boot 3.3+, Spring Data JPA, Spring Security 6 (JWT & BCrypt), Virtual Threads
- **Background Worker**: JobRunr with embedded worker & monitoring dashboard (port `8000`)
- **Document & OCR Engine**: Apache PDFBox 3.x + Tess4J (Tesseract OCR)
- **Database**: PostgreSQL 15 with native Row-Level Security (RLS) multi-tenant policies
- **Database Migrations**: Flyway SQL (`V1__initial_schema.sql`)
- **Cache & Pub/Sub**: Redis 7
- **Frontend**: Pure HTML, CSS, JavaScript, and React 18 (Vite, dual HR & Client portals)
- **Containerization**: Multi-stage Dockerfiles (`backend-java/Dockerfile`, `frontend/Dockerfile`) & Docker Compose

---

## 🏛 System Architecture

```
                       ┌─────────────────────────┐
                       │   React 18 SPA (Vite)   │
                       │   HR & Client Portals   │
                       └────────────┬────────────┘
                                    │ HTTP / REST / SSE
                                    ▼
                       ┌─────────────────────────┐
                       │   Spring Boot 3 API     │
                       │    (Java 21 / Port 8080)│
                       └───────┬───────────┬─────┘
                               │           │
            JobRunr / Ingestion│           │Flyway + RLS HikariCP
                               ▼           ▼
                       ┌───────────┐   ┌─────────────────────────┐
                       │  Redis 7  │   │  PostgreSQL 15 (RLS)    │
                       └───────────┘   └─────────────────────────┘
```

---

## ⚡ Quick Start with Docker Compose

To boot the complete stack (PostgreSQL, Redis, Java backend, and React frontend):

```bash
docker compose up -d --build
```

### Service Endpoints:
- **Web Application (React)**: [http://localhost:3000](http://localhost:3000)
- **REST API & Swagger UI**: [http://localhost:8080/swagger-ui.html](http://localhost:8080/swagger-ui.html)
- **OpenAPI JSON Spec**: [http://localhost:8080/api-docs](http://localhost:8080/api-docs)
- **JobRunr Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Spring Actuator Health**: [http://localhost:8080/actuator/health](http://localhost:8080/actuator/health)

---

## 🛠 Local Development Setup

### 1. Prerequisites
- Java 21 JDK (or Eclipse Temurin 21)
- Maven 3.9+
- Node.js 20+ & npm
- PostgreSQL 15 running locally or via Docker

### 2. Backend (Java Spring Boot)
```bash
cd backend-java
mvn clean spring-boot:run
```

### 3. Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
Development frontend will start at [http://localhost:5173](http://localhost:5173).
