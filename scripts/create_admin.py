import sys
import os
from uuid import uuid4

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from ats_backend.core.database import db_manager
from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.auth.utils import get_password_hash

def create_admin():
    print("Initializing DB...")
    db_manager.initialize()
    
    try:
        with db_manager.get_session() as session:
            # Check if client exists
            client = session.query(Client).filter(Client.name == "Acme Corp").first()
            if not client:
                print("Creating client 'Acme Corp'...")
                client = Client(
                    id=uuid4(),
                    name="Acme Corp",
                    domain="acmecorp.com",
                    is_active=True
                )
                session.add(client)
                session.flush()
                print(f"Client created: {client.id}")
            else:
                print(f"Client found: {client.id}")
                
            # Check if user exists
            email = "admin@acmecorp.com"
            user = session.query(User).filter(User.email == email).first()
            if user:
                print("User already exists")
                # Update password just in case
                user.hashed_password = get_password_hash("admin123")
                session.add(user)
                print("User password updated")
            else:
                print("Creating user 'admin@acmecorp.com'...")
                user = User(
                    id=uuid4(),
                    email=email,
                    hashed_password=get_password_hash("admin123"),
                    full_name="Admin User",
                    client_id=client.id,
                    is_active=True
                )
                session.add(user)
                print("User created")
                
            session.commit()
            print("Done.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db_manager.close()

if __name__ == "__main__":
    create_admin()
