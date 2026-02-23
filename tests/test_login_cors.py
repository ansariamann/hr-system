import requests

def test_login_cors():
    url = "http://127.0.0.1:8000/auth/login"
    headers = {
        "Origin": "http://localhost:5174",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "username": "admin@acmecorp.com",
        "password": "admin123"
    }
    
    print(f"Testing POST {url}")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    
    try:
        response = requests.post(url, headers=headers, data=data)
        
        print(f"Status: {response.status_code}")
        print("Response Headers:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
        
        print("\nBody:")
        print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login_cors()
