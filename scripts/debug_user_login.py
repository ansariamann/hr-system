import sys
import os
import requests

# Add src to path so we can import ats_backend
sys.path.append(os.path.join(os.getcwd(), "src"))

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User
from ats_backend.auth.utils import verify_password

def check_user(email, password):
    print(f"Initializing database manager...")
    try:
        db_manager.initialize()
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        # It might happen if settings are missing
        return

    print(f"Checking user: {email}")
    try:
        db = db_manager.SessionLocal()
    except Exception as e:
        print(f"Failed to create session: {e}")
        return

    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User {email} not found in database!")
            return
        
        print(f"User found: ID={user.id}, Email={user.email}")
        print(f"Hashed Password in DB: {user.hashed_password}")
        print(f"Is Active: {user.is_active}")
        
        try:
            is_valid = verify_password(password, user.hashed_password)
            print(f"Password '{password}' verification result: {is_valid}")
        except Exception as e:
            print(f"Error verifying password: {e}")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        db.close()
        db_manager.close()

    # Try HTTP login
    print("\n--- Testing HTTP Login ---")
    url = "http://localhost:8000/auth/login"
    payload = {
        "username": email,
        "password": password
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        print(f"POST {url} with username={email}")
        response = requests.post(url, data=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"HTTP Request failed: {e}")

if __name__ == "__main__":
    check_user("admin@acmecorp.com", "admin123")
