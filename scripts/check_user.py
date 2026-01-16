import sys
import os
from sqlalchemy import text

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User
from ats_backend.auth.utils import verify_password

def check_user():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
        if not user:
            print("User admin@acmecorp.com NOT FOUND.")
        else:
            print(f"User Found: {user.email} (ID: {user.id})")
            print(f"Is Active: {user.is_active}")
            print(f"Client ID: {user.client_id}")
            
            # Verify password
            is_valid = verify_password("admin123", user.hashed_password)
            print(f"Password 'admin123' valid: {is_valid}")
            
            if not is_valid:
                 print(f"Hashed pwd: {user.hashed_password}")

if __name__ == "__main__":
    check_user()
