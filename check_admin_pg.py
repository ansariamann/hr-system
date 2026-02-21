
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set environment variables for PostgreSQL connection
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "ats_db"
os.environ["POSTGRES_USER"] = "ats_user"
os.environ["POSTGRES_PASSWORD"] = "ats_dev_password_2024"
os.environ["CUSTOM_DATABASE_URL"] = "postgresql://ats_user:ats_dev_password_2024@localhost:5432/ats_db"

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User

def check_admin():
    try:
        print("Connecting to database...")
        db_manager.initialize()
        
        with db_manager.get_session() as db:
            print("Checking for admin user 'admin@acmecorp.com'...")
            user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
            
            if user:
                print(f"User found: {user.email}")
                print(f"ID: {user.id}")
                print(f"Is Active: {user.is_active}")
                print(f"Client ID: {user.client_id}")
            else:
                print("User 'admin@acmecorp.com' NOT found.")
                
    except Exception as e:
        print(f"Error checking admin user: {e}")

if __name__ == "__main__":
    check_admin()
