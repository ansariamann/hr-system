import requests

def test_login_payload():
    url = "http://localhost:8000/auth/login"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "http://localhost:5174"
    }
    # Matches PortalLogin.tsx exactly
    data = {
        "username": "admin@acmecorp.com",
        "password": "admin123"
    }
    
    print(f"Testing Login Payload: {url}")
    try:
        response = requests.post(url, headers=headers, data=data)
        print(f"Status: {response.status_code}")
        try:
            print(f"Body: {response.json()}")
        except:
            print(f"Body: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_login_payload()
