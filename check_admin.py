
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))

from sqlalchemy import create_engine, text
from ats_backend.core.config import settings

# Adjust the database URL if needed (e.g. for drivers not installed in this environment)
# Assuming standard postgres or sqlite. The config should handle it.
print(f"Database URL: {settings.DATABASE_URL}")

try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT id, email, is_active, is_superuser FROM users WHERE email = 'admin@acmecorp.com'"))
        user = result.fetchone()
        
        if user:
            print(f"User found: {user}")
        else:
            print("User 'admin@acmecorp.com' not found.")
            
            # List all users just in case
            print("Listing all users:")
            result_all = connection.execute(text("SELECT id, email FROM users"))
            for u in result_all:
                print(u)
                
except Exception as e:
    print(f"Error connecting to database: {e}")
