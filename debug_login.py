
import requests
import json

url = "http://localhost:8000/auth/login"
payload = {
    "username": "admin@acmecorp.com",
    "password": "admin123"
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    # Emulate browser origin just in case
    "Origin": "http://localhost:5174"
}

try:
    print(f"POST {url}")
    print(f"Data: {payload}")
    response = requests.post(url, data=payload, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print(f"Headers: {response.headers}")
    
except Exception as e:
    print(f"Error: {e}")
