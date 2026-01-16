
import requests

try:
    print("Testing CORS for http://localhost:5174...")
    response = requests.get(
        "http://localhost:8000/health",
        headers={"Origin": "http://localhost:5174"}
    )
    
    print(f"Status Code: {response.status_code}")
    print("Headers:")
    for k, v in response.headers.items():
        if 'access-control' in k.lower():
            print(f"{k}: {v}")
            
    if response.headers.get("access-control-allow-origin") == "http://localhost:5174":
        print("SUCCESS: CORS header present and correct.")
    else:
        print("FAILURE: CORS header missing or incorrect.")
        
except Exception as e:
    print(f"Error: {e}")
