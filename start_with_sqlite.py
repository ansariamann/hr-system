"""Start FastAPI with SQLite database (bypassing PostgreSQL checks)."""
import os
import sys

# Set environment variables BEFORE importing anything
os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"  # Bypass validation check
os.environ["LOG_LEVEL"] = "INFO"

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "ats_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
