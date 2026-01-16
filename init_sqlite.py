
import os
import sys

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Override env var BEFORE importing settings
os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"

from ats_backend.core.config import settings
from ats_backend.core.database import db_manager, Base
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.auth.utils import get_password_hash
import uuid
from sqlalchemy.orm import Session

def init_sqlite():
    print(f"Using DB URL: {settings.database_url}")
    
    # force initialize with new url
    db_manager.database_url = settings.database_url
    db_manager.initialize()
    
    print("Creating tables...")
    # Bind engine to metadata
    Base.metadata.create_all(bind=db_manager.engine)
    
    session = db_manager.SessionLocal()
    try:
        # Create Client
        client = Client(
            id=uuid.uuid4(),
            name="Acme Corp",
            email_domain="acmecorp.com"
        )
        session.add(client)
        session.commit()
        print(f"Created Client: {client.id}")
        
        # Create User
        user = User(
            id=uuid.uuid4(),
            email="admin@acmecorp.com",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            client_id=client.id
        )
        session.add(user)
        session.commit()
        print("Created Admin User: admin@acmecorp.com / admin123")
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_sqlite()
