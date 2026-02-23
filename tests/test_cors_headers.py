import requests

# Test CORS headers on login endpoint
url = "http://localhost:8000/auth/login"
headers = {
    "Origin": "http://localhost:5174",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type"
}

print("Testing OPTIONS (preflight) request...")
response = requests.options(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"CORS Headers:")
for key, value in response.headers.items():
    if 'access-control' in key.lower() or 'origin' in key.lower():
        print(f"  {key}: {value}")

print("\n" + "="*50 + "\n")

print("Testing POST request with Origin header...")
response = requests.post(
    url,
    data={"username": "admin@acmecorp.com", "password": "admin123"},
    headers={"Origin": "http://localhost:5174"}
)
print(f"Status: {response.status_code}")
print(f"CORS Headers:")
for key, value in response.headers.items():
    if 'access-control' in key.lower() or 'origin' in key.lower():
        print(f"  {key}: {value}")
