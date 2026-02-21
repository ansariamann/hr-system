
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set environment variables for SQLite connection
os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User
from ats_backend.models.client import Client
import uuid
from ats_backend.auth.utils import get_password_hash

def check_and_seed_sqlite():
    try:
        print("Connecting to SQLite database...")
        db_manager.initialize()
        db_manager.create_tables() # Create tables if they don't exist
        
        with db_manager.get_session() as db:
            print("Checking for admin user 'admin@acmecorp.com'...")
            user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
            
            if user:
                print(f"User found: {user.email}")
            else:
                print("User 'admin@acmecorp.com' NOT found. Seeding...")
                # Check/Create Client
                client = db.query(Client).filter(Client.name == "Acme Corp").first()
                if not client:
                    client = Client(
                        id=uuid.uuid4(),
                        name="Acme Corp",
                        email_domain="acmecorp.com"
                    )
                    db.add(client)
                    db.flush()
                
                # Create User
                user = User(
                    id=uuid.uuid4(),
                    email="admin@acmecorp.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Admin User",
                    client_id=client.id,
                    is_active=True
                )
                db.add(user)
                db.commit()
                print("Admin user created successfully.")
                
    except Exception as e:
        print(f"Error checking/seeding SQLite: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_and_seed_sqlite()
