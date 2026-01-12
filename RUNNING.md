# How to Run the Project

This project consists of a Python FastAPI backend and a React/Vite frontend.

## Prerequisites

- **Docker Desktop** (for database and redis)
- **Node.js** (v18+ recommended)
- **Python** (3.11+ recommended)

---

## 1. Backend Setup

The backend handles the API, database (PostgreSQL), and background workers (Celery/Redis).

### Option A: Docker (Recommended)

This is the easiest way to get the backend services (API, DB, Redis, Worker) running.

1.  Make sure Docker Desktop is running.
2.  Open a terminal in the project root (`hr-system`).
3.  Run the services:
    ```powershell
    docker-compose up -d
    ```
4.  The backend API will be available at [http://localhost:8000](http://localhost:8000).
5.  API Documentation (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs).
6.  Celery Flower (Monitoring): [http://localhost:5555](http://localhost:5555) (if using profile `dev`).

### Option B: Local Development (Manual)

If you prefer to run Python services locally (e.g., for debugging):

1.  **Start Infrastructure**: You still need Postgres and Redis.
    ```powershell
    docker-compose up -d postgres redis
    ```
2.  **Setup Python Environment**:
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate
    pip install -e .[dev]
    ```
3.  **Run Migrations**:
    ```powershell
    alembic upgrade head
    ```
4.  **Run API Server**:
    ```powershell
    uvicorn ats_backend.main:app --reload --host 0.0.0.0 --port 8000
    ```
5.  **Run Celery Worker** (in a separate terminal):
    ```powershell
    celery -A ats_backend.worker.celery_app worker --loglevel=info
    ```

---

## 2. Frontend Setup

The frontend is a React application using Vite.

1.  Open a **new terminal** and navigate to the frontend directory:
    ```powershell
    cd frontend
    ```
2.  **Install Dependencies**:
    ```powershell
    npm install
    ```
3.  **Start Dev Server**:
    ```powershell
    npm run dev
    ```
4.  Access the application at [http://localhost:5173](http://localhost:5173).

## 3. Accessing the App

- **Client Portal**: [http://localhost:5173/portal](http://localhost:5173/portal)
- **HR Dashboard**: [http://localhost:5173/admin](http://localhost:5173/admin)
- **Login Credentials**:
    - Ensure you have created users via the backend API or seed scripts if available.
