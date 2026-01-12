import sys
import os
import uuid
from sqlalchemy.orm import Session

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.auth.utils import get_password_hash

def seed():
    print("Initializing database...")
    db_manager.initialize()
    
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
            print(f"Client created with ID: {client.id}")
        else:
            print(f"Client found: {client.id}")
            
        print("Checking for existing user...")
        user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
        if not user:
            print("Creating user admin@acmecorp.com...")
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
            print("User created successfully.")
        else:
            print("User already exists. Updating password...")
            user.hashed_password = get_password_hash("admin123")
            db.commit()
            print("Password updated.")

if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"Error seeding database: {e}")
        import traceback
        traceback.print_exc()
