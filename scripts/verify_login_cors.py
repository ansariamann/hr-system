import requests
import sys

def verify_login_cors():
    url = "http://localhost:8000/auth/login"
    headers = {
        "Origin": "http://localhost:5174",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "username": "admin@acmecorp.com",
        "password": "admin123"
    }
    
    print(f"Testing CORS/Login: {url}")
    print(f"Origin: {headers['Origin']}")
    
    try:
        # Check OPTIONS (Preflight)
        print("\nSending OPTIONS request...")
        options_response = requests.options(url, headers={"Origin": "http://localhost:5174", "Access-Control-Request-Method": "POST"})
        print(f"OPTIONS Status: {options_response.status_code}")
        print("OPTIONS Headers:")
        for k, v in options_response.headers.items():
            if "Access-Control" in k:
                print(f"  {k}: {v}")
        print(f"OPTIONS Body: {options_response.text}")

        # Check POST (Login)
        print("\nSending POST request...")
        response = requests.post(url, headers=headers, data=data)
        
        print(f"POST Status: {response.status_code}")
        print("POST Headers:")
        for k, v in response.headers.items():
            if "Access-Control" in k:
                print(f"  {k}: {v}")
        
        if "Access-Control-Allow-Origin" not in response.headers:
            print("\nERROR: Missing Access-Control-Allow-Origin header!")
        else:
            print(f"\nAccess-Control-Allow-Origin: {response.headers['Access-Control-Allow-Origin']}")
            
        if response.status_code == 200:
            print("Login Successful")
            print(f"Response: {response.json()}")
        else:
            print("Login Failed")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    verify_login_cors()
