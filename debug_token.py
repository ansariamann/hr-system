"""Test token verification directly."""
import os
import sys
import requests

# Step 1: Get a token
print("1. Getting token via login...")
r = requests.post("http://localhost:8000/auth/login", data={
    "username": "admin@acmecorp.com",
    "password": "admin123"
})
token = r.json()["access_token"]
print(f"   Token received: {token[:50]}...")

# Step 2: Decode and verify the token locally
print("\n2. Decoding token locally (without verification)...")
import base64
import json

# Split JWT into parts
parts = token.split(".")
if len(parts) == 3:
    # Decode payload (middle part)
    payload_b64 = parts[1]
    # Add padding if needed
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload_json = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_json)
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    
    # Check user_id in payload
    user_id = payload.get("sub")
    client_id = payload.get("client_id")
    email = payload.get("email")
    print(f"\n   Extracted:")
    print(f"     user_id (sub): {user_id}")
    print(f"     client_id: {client_id}")
    print(f"     email: {email}")
else:
    print("   ERROR: Invalid JWT token format")
