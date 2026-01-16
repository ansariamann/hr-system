"""Full backend test with token verification."""
import os
import sys
import json

os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import requests

# Step 1: Get a token
print("1. Getting token via login...")
r = requests.post("http://localhost:8000/auth/login", data={
    "username": "admin@acmecorp.com",
    "password": "admin123"
})
token = r.json()["access_token"]
print(f"   Token: {token[:40]}...")

# Step 2: Test verify_token directly
print("\n2. Testing verify_token locally...")
from ats_backend.auth.utils import verify_token
from ats_backend.core.database import SessionLocal
import asyncio

db = SessionLocal()
try:
    token_data = asyncio.run(verify_token(token, db))
    if token_data:
        print(f"   Token valid!")
        print(f"   user_id: {token_data.user_id}")
        print(f"   client_id: {token_data.client_id}")
        print(f"   email: {token_data.email}")
    else:
        print("   verify_token returned None!")
except Exception as e:
    print(f"   ERROR: {e}")
finally:
    db.close()

# Step 3: Check if user can be retrieved
print("\n3. Testing get_user_by_id...")
from ats_backend.auth.utils import get_user_by_id
from uuid import UUID

if token_data:
    db = SessionLocal()
    try:
        user = get_user_by_id(db, token_data.user_id)
        if user:
            print(f"   User found: {user.email}")
            print(f"   Is Active: {user.is_active}")
            print(f"   Client ID: {user.client_id}")
        else:
            print("   User NOT FOUND!")
    finally:
        db.close()
