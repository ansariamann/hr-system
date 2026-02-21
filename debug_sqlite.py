
import os
import sys

# Set environment variables for SQLite connection
os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from ats_backend.core.config import settings
print(f"DEBUG: settings.database_url = {settings.database_url}")
print(f"DEBUG: os.environ['CUSTOM_DATABASE_URL'] = {os.environ.get('CUSTOM_DATABASE_URL')}")

from sqlalchemy import create_engine, text

def test_sqlite():
    db_url = "sqlite:///./temp_dev.db"
    print(f"Testing direct connection to {db_url}...")
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Direct connection successful.")
    except Exception as e:
        print(f"Direct connection failed: {e}")

if __name__ == "__main__":
    test_sqlite()
    
    # Now try with db_manager
    from ats_backend.core.database import db_manager
    print(f"db_manager.database_url: {db_manager.database_url}")
    
    try:
        db_manager.initialize()
        print("db_manager initialized.")
    except Exception as e:
        print(f"db_manager initialization failed: {e}")
