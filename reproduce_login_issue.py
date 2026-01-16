import requests
import sys

BASE_URL = "http://localhost:8000" 
EMAIL = "admin@acmecorp.com"
PASSWORD = "admin123"

def test_login():
    print(f"Attempting login to {BASE_URL}/auth/login with {EMAIL}...")
    try:
        response = requests.post(f"{BASE_URL}/auth/login", data={
            "username": EMAIL,
            "password": PASSWORD
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        print(f"Login Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Login Failed: {response.text}")
            return None
            
        data = response.json()
        token = data.get("access_token")
        print(f"Got Token: {token[:20]}...")
        
        # Decode token payload
        try:
            import base64
            import json
            parts = token.split('.')
            payload = parts[1]
            padded = payload + '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            print(f"Token Payload: {json.dumps(json.loads(decoded), indent=2)}")
        except Exception as e:
            print(f"Failed to decode token: {e}")
            
        return token
    except Exception as e:
        print(f"Login Exception: {e}")
        return None

def test_auth_me(token):
    print(f"\nAttempting to access {BASE_URL}/auth/me...")
    try:
        response = requests.get(f"{BASE_URL}/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        print(f"Auth Me Status: {response.status_code}")
        print(f"Auth Me Response: {response.text}")
    except Exception as e:
        print(f"Auth Me Exception: {e}")

if __name__ == "__main__":
    token = test_login()
    if token:
        test_auth_me(token)
