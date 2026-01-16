"""Test server with full middleware but debug output."""
import os
import sys

os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"
os.environ["LOG_LEVEL"] = "DEBUG"

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Patch CORS middleware to add debug
original_preflight = CORSMiddleware.preflight_response
def debug_preflight(self, request_headers):
    origin = request_headers.get("origin", "NONE")
    print(f"DEBUG: preflight_response called with origin: {repr(origin)}")
    print(f"DEBUG: allow_origins: {self.allow_origins}")
    print(f"DEBUG: is_allowed_origin: {self.is_allowed_origin(origin)}")
    result = original_preflight(self, request_headers)
    print(f"DEBUG: preflight response status: {result.status_code}")
    return result
CORSMiddleware.preflight_response = debug_preflight

# Import the actual app
from ats_backend.main import app, ALLOWED_ORIGINS

print(f"Starting with ALLOWED_ORIGINS = {ALLOWED_ORIGINS}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
