import requests
from jose import jwt
import json
import sys
import base64
from datetime import datetime
import time

# Backend URL (Docker)
API_URL = "http://localhost:8000"
LOGIN_URL = f"{API_URL}/auth/login"
INGEST_URL = f"{API_URL}/email/ingest"
CANDIDATES_URL = f"{API_URL}/candidates"

CREDENTIALS = {
    "username": "admin@acmecorp.com",
    "password": "admin123"
}

def test_ingestion():
    print(f"Logging in to {LOGIN_URL}...")
    try:
        response = requests.post(LOGIN_URL, data=CREDENTIALS)
        if response.status_code != 200:
            print(f"Login failed: {response.status_code} {response.text}")
            return

        token_data = response.json()
        token = token_data.get("access_token")
        print(f"Got token.")

        # Decode to get client_id
        payload = jwt.get_unverified_claims(token)
        client_id = payload.get("client_id")
        print(f"Client ID: {client_id}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Initial Candidate Count
        print("Fetching initial candidate count...")
        cand_resp = requests.get(CANDIDATES_URL, headers=headers)
        initial_count = 0
        if cand_resp.status_code == 200:
            data = cand_resp.json()
            items = data if isinstance(data, list) else (data.get("items", []) or data.get("data", []))
            initial_count = len(items)
            print(f"Initial count: {initial_count}")
        else:
            print(f"Failed to fetch candidates: {cand_resp.text}")

        # Prepare Ingestion Payload
        # Minimal valid PDF base64
        MINIMAL_PDF_B64 = "JVBERi0xLjQKJcfsj6IKNSAwIG9iago8PC9MZW5ndGggNiAwIFIvRmlsdGVyIC9GbGF0ZURlY29kZT4+CnN0cmVhbQp4nGNiYGBgYGQAAwEBAQAAAAEAAQplbmRzdHJlYW0KZW5kb2JqCjYgMCBvYmoKOTIKZW5kb2JqCjQgMCBvYmoKPDwvVHlwZSAvUGFnZSAvUGFyZW50IDMgMCBSIC9NZWRpYUJveCBbMCAwIDYxMiA3OTJdIC9Db250ZW50cyA1IDAgUgovUmVzb3VyY2VzIDw8L1Byb2NTZXQgWy9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUldPj4+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlIC9QYWdlcyAvS2lkcyBbNCAwIFJdIC9Db3VudCAxPj4KZW5kb2JqCjIgMCBvYmoKPDwvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMyAwIFI+PgplbmRvYmoKMSAwIG9iago8PC9DcmVhdG9yIChQZGZNZWtlcikgL1Byb2R1Y2VyIChQZGZNZWtlcikgL0NyZWF0aW9uRGF0ZSAoRDoyMDIwMDEwMTAwMDAwMCk+PgplbmRvYmoKeHJlZgowIDcKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMzM2IDAwMDAwIG4gCjAwMDAwMDAyODcgMDAwMDAgbiAKMDAwMDAwMDIyOCAwMDAwMCBuIAowMDAwMDAwMTA5IDAwMDAwIG4gCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA5MCAwMDAwMCBuIAp0cmFpbGVyCjw8L1NpemUgNyAvUm9vdCAyIDAgUiAvSW5mbyAxIDAgUj4+CnN0YXJ0eHJlZgo0MDkKJSVFT0YK"
        
        ingest_payload = {
            "client_id": client_id,
            "email": {
                "message_id": f"msg_{int(time.time())}",
                "sender": "sender@example.com",
                "subject": "Resume Application via Test",
                "body": "Please find attached resume.",
                "received_at": datetime.now().isoformat(),
                "attachments": [
                    {
                        "filename": "resume_test.pdf",
                        "content_type": "application/pdf",
                        "content": MINIMAL_PDF_B64,
                        "size": len(base64.b64decode(MINIMAL_PDF_B64))
                    }
                ]
            }
        }

        print(f"Sending ingestion request to {INGEST_URL}...")
        ingest_resp = requests.post(INGEST_URL, json=ingest_payload, headers=headers)
        
        if ingest_resp.status_code != 200:
            print(f"Ingestion Failed: {ingest_resp.status_code} {ingest_resp.text}")
            return

        print("Ingestion request successful. Response:")
        print(json.dumps(ingest_resp.json(), indent=2))

        # Poll for candidate creation
        print("Polling for candidate count increase (waiting 10s)...")
        for i in range(10):
            time.sleep(1)
            cand_resp = requests.get(CANDIDATES_URL, headers=headers)
            if cand_resp.status_code == 200:
                data = cand_resp.json()
                items = data if isinstance(data, list) else (data.get("items", []) or data.get("data", []))
                new_count = len(items)
                if new_count > initial_count:
                    print(f"SUCCESS! Candidate count increased to {new_count}")
                    return
                # print(f"Count: {new_count}...")
        
        print(f"TIMEOUT: Candidate count did NOT increase after 10s. Still {initial_count}.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ingestion()
