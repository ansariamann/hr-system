
import requests
import json

BASE_URL = "http://localhost:8000"

def verify_login():
    url = f"{BASE_URL}/auth/login"
    # Content-Type: application/x-www-form-urlencoded
    data = {
        "username": "admin@acmecorp.com",
        "password": "admin123"
    }
    
    print(f"Attempting login to {url} with {data['username']}...")
    try:
        response = requests.post(url, data=data)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            token = response.json()
            print("Login Successful!")
            print(f"Token Type: {token.get('token_type')}")
            print(f"Access Token: {token.get('access_token')[:20]}...")
        else:
            print("Login Failed!")
            print(response.text)
            
    except Exception as e:
        print(f"Error during login verification: {e}")

if __name__ == "__main__":
    verify_login()
