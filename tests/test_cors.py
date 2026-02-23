import requests

def test_cors():
    url = "http://localhost:8000/auth/login"
    headers = {
        "Origin": "http://localhost:5174",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"
    }
    
    print(f"Testing OPTIONS {url}")
    print(f"Headers: {headers}")
    
    try:
        response = requests.options(url, headers=headers)
        
        print(f"Status: {response.status_code}")
        print("Response Headers:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
        print(f"Body: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_cors()
