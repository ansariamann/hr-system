"""Simple API test script."""
import requests
import time

print("Waiting for server to be ready...")
time.sleep(2)

try:
    print("\n1. Testing health endpoint...")
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    print("   ✓ Health endpoint working!")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\nDone!")
