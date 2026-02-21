import requests
from jose import jwt
import json
import sys

# Backend URL (Docker)
API_URL = "http://localhost:8000"
LOGIN_URL = f"{API_URL}/auth/login"

CREDENTIALS = {
    "username": "admin@acmecorp.com",
    "password": "admin123"
}

def debug_token():
    print(f"Logging in to {LOGIN_URL}...")
    try:
        response = requests.post(LOGIN_URL, data=CREDENTIALS)
        if response.status_code != 200:
            print(f"Login failed: {response.status_code} {response.text}")
            return

        token_data = response.json()
        token = token_data.get("access_token")
        print(f"Got token: {token[:20]}...")

        # Decode without verification to see payload
        try:
            payload = jwt.get_unverified_claims(token)
            print("\nToken Payload:")
            print(json.dumps(payload, indent=2))
            
            if "client_id" not in payload:
                print("\nCRITICAL: client_id MISSING from token payload!")
            else:
                print(f"\nclient_id found: {payload['client_id']}")
                
            if "sub" not in payload:
                 print("\nCRITICAL: sub (user_id) MISSING from token payload!")
            else:
                print(f"user_id (sub) found: {payload['sub']}")

            # Test candidates endpoint
            print(f"\nTesting {API_URL}/candidates...")
            headers = {"Authorization": f"Bearer {token}"}
            cand_resp = requests.get(f"{API_URL}/candidates", headers=headers)
            print(f"Candidates response: {cand_resp.status_code}")
            if cand_resp.status_code != 200:
                print(f"Error: {cand_resp.text}")
            else:
                data = cand_resp.json()
                if isinstance(data, list):
                    items = data
                    total = len(data)
                else:
                    items = data.get("items", []) or data.get("data", [])
                    total = data.get('total', 'unknown')
                
                print(f"Candidates request SUCCESS! Count: {len(items)}")
                print(f"Total: {total}")

        except Exception as e:
            print(f"Error decoding token or requesting candidates: {e}")

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    debug_token()
