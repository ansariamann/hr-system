if __name__ == "__main__":
    import os
    import uvicorn
    
    # Force PostgreSQL configuration for local execution against Docker
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    os.environ["POSTGRES_DB"] = "ats_db"
    os.environ["POSTGRES_USER"] = "ats_user"
    os.environ["POSTGRES_PASSWORD"] = "ats_dev_password_2024"
    
    # Ensure SECRET_KEY matches .env
    os.environ["SECRET_KEY"] = "dev_jwt_secret_key_ats_2024_very_long_and_secure"
    
    # Force CUSTOM_DATABASE_URL to override any .env file settings that might point to sqlite
    # This is crucial because pydantic-settings might load from .env even if we delete from os.environ
    os.environ["CUSTOM_DATABASE_URL"] = "postgresql://ats_user:ats_dev_password_2024@localhost:5432/ats_db"

    # Import settings AFTER setting environment variables to ensure they are picked up
    from ats_backend.core.config import settings

    print("Starting ATS Backend with LOCALHOST PostgreSQL...")
    print(f"Database URL: {settings.database_url}")
    
    uvicorn.run(
        "ats_backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="debug"
    )
