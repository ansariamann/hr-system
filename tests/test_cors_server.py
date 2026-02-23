"""Minimal test server for CORS debugging."""
import os
import sys

os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create minimal app
app_test = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
]

app_test.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app_test.post("/auth/login")
async def login():
    return {"message": "Login OK"}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting with allowed origins: {ALLOWED_ORIGINS}")
    uvicorn.run(app_test, host="0.0.0.0", port=8000)
