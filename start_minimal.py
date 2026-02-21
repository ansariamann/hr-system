"""Start FastAPI with minimal configuration for debugging."""
import os
import sys

# Set environment variables BEFORE importing anything
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "ats_db"
os.environ["POSTGRES_USER"] = "ats_user"
os.environ["POSTGRES_PASSWORD"] = "ats_dev_password_2024"
os.environ["SECRET_KEY"] = "dev_jwt_secret_key_ats_2024_very_long_and_secure"
os.environ["CUSTOM_DATABASE_URL"] = "postgresql://ats_user:ats_dev_password_2024@localhost:5432/ats_db"

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Create minimal app
app = FastAPI(title="ATS Backend API - Minimal", version="0.1.0")

# Add CORS
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8081",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {"message": "ATS Backend API - Minimal Mode"}

# Import and include routers
try:
    from ats_backend.api.candidates import router as candidates_router
    from ats_backend.api.applications import router as applications_router
    from ats_backend.api.email import router as email_router
    
    app.include_router(candidates_router)
    app.include_router(applications_router)
    app.include_router(email_router)
    print("[OK] API routers loaded")
except Exception as e:
    print(f"[ERROR] Error loading routers: {e}")

if __name__ == "__main__":
    print("Starting ATS Backend in MINIMAL mode...")
    print("This bypasses all middleware for debugging")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
