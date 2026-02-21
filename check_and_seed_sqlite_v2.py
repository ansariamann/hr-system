
import os
import sys

# Set environment variables for SQLite connection BEFORE any other imports
os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"
os.environ["POSTGRES_USER"] = "dummy"
os.environ["POSTGRES_DB"] = "dummy"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from ats_backend.core.database import db_manager, Base
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.auth.utils import get_password_hash
import uuid

def check_and_seed_sqlite():
    try:
        print("Initializing SQLite database...")
        # Force re-initialization with SQLite URL if needed, although env var should handle it
        # print(f"Database URL: {db_manager.database_url}") 
        
        db_manager.initialize()
        db_manager.create_tables()
        print("Tables created.")
        
        with db_manager.get_session() as db:
            print("Checking for existing client...")
            client = db.query(Client).filter(Client.name == "Acme Corp").first()
            if not client:
                print("Creating client Acme Corp...")
                client = Client(
                    id=uuid.uuid4(),
                    name="Acme Corp",
                    email_domain="acmecorp.com"
                )
                db.add(client)
                db.flush()
                print(f"Client created: {client.id}")
            else:
                print(f"Client found: {client.id}")

            print("Checking for admin user 'admin@acmecorp.com'...")
            user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
            
            if user:
                print(f"User found: {user.email}")
                # Reset password to ensure it is known
                user.hashed_password = get_password_hash("admin123")
                db.add(user)
                db.commit()
                print("User password reset to 'admin123'.")
            else:
                print("User 'admin@acmecorp.com' NOT found. Creating...")
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
