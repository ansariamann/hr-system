
from ats_backend.auth.utils import verify_password, get_password_hash
from ats_backend.core.database import db_manager
from ats_backend.auth.models import User
import sys
import os

# Add src to path if not present
sys.path.append(os.path.join(os.getcwd(), "src"))

# Test generic
try:
    print("Testing 'admin123'...")
    h = get_password_hash("admin123")
    print(f"Hash: {h}")
    v = verify_password("admin123", h)
    print(f"Verify: {v}")
except Exception as e:
    print(f"Generic test failed: {e}")

# Test DB user
try:
    db_manager.initialize()
    SessionLocal = db_manager.SessionLocal
    db = SessionLocal()
    user = db.query(User).filter(User.email == "admin@acmecorp.com").first()
    if user:
        print(f"User found: {user.email}")
        print(f"Stored hash: {user.hashed_password}")
        print(f"Hash length: {len(user.hashed_password)}")
        try:
            v = verify_password("admin123", user.hashed_password)
            print(f"Verify admin123 against DB hash: {v}")
        except Exception as e:
            print(f"Verification failed: {e}")
            
        import bcrypt
        try:
            print(f"Type of stored hash: {type(user.hashed_password)}")
            stored_hash_bytes = user.hashed_password.encode('utf-8')
            print(f"Stored hash bytes: {stored_hash_bytes}")
            
            # Try direct bcrypt
            try:
                result = bcrypt.checkpw(b"admin123", stored_hash_bytes)
                print(f"Direct bcrypt check: {result}")
            except Exception as be:
                print(f"Direct bcrypt check failed: {be}")
        except Exception as e:
            print(f"Direct bcrypt setup failed: {e}")
    else:
        print("User admin@acmecorp.com not found")
except Exception as e:
    print(f"DB test failed: {e}")
