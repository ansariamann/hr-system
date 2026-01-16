"""Test the complete auth flow."""
import requests

print("=== Testing Auth Flow ===")
print()

# Step 1: Login
print("1. Testing login...")
r = requests.post("http://localhost:8000/auth/login", data={
    "username": "admin@acmecorp.com",
    "password": "admin123"
})
print(f"   Login Status: {r.status_code}")

if r.status_code != 200:
    print(f"   Error: {r.text}")
    exit(1)

data = r.json()
token = data.get("access_token")
print(f"   Token received: Yes (length={len(token)})")

# Step 2: Test /auth/me
print()
print("2. Testing /auth/me with token...")
r2 = requests.get("http://localhost:8000/auth/me", headers={
    "Authorization": f"Bearer {token}"
})
print(f"   Status: {r2.status_code}")
print(f"   Response: {r2.text}")

if r2.status_code == 401:
    print()
    print("   *** TOKEN VALIDATION FAILED - This is causing the auto-logout! ***")
else:
    print()
    print("   Token is valid - auth flow should work")
