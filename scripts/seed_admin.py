#!/usr/bin/env python3
"""Seed database with default admin user."""

import sys
from pathlib import Path
from uuid import uuid4

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.database import db_manager, init_db
from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.auth.utils import get_password_hash
import structlog

logger = structlog.get_logger(__name__)

def seed_admin():
    try:
        # Initialize DB connection
        db_manager.initialize()
        
        with db_manager.get_session() as session:
            # Check if client exists
            client = session.query(Client).filter(Client.name == "Acme Corp").first()
            if not client:
                client = Client(
                    id=uuid4(),
                    name="Acme Corp",
                    email_domain="acmecorp.com"
                )
                session.add(client)
                session.flush()
                print(f"Created Client: {client.name}")
            else:
                print(f"Client {client.name} already exists")
            
            # Check if user exists
            admin_email = "admin@acmecorp.com"
            user = session.query(User).filter(User.email == admin_email).first()
            
            if not user:
                user = User(
                    id=uuid4(),
                    email=admin_email,
                    hashed_password=get_password_hash("admin123"),
                    full_name="System Admin",
                    client_id=client.id,
                    is_active=True
                )
                session.add(user)
                session.commit()
                print(f"Created User: {user.email} / admin123")
            else:
                print(f"User {user.email} already exists - Updating password")
                user.hashed_password = get_password_hash("admin123")
                session.add(user)
                session.commit()
                
    except Exception as e:
        print(f"Error seeding database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    seed_admin()
