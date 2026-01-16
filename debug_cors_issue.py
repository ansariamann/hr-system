"""Debug CORS issue by testing middleware directly."""
import os
import sys

os.environ["CUSTOM_DATABASE_URL"] = "sqlite:///./temp_dev.db"
os.environ["POSTGRES_PASSWORD"] = "dummy"

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from ats_backend.main import app, ALLOWED_ORIGINS

output = []
output.append("=== ALLOWED_ORIGINS from main.py ===")
for i, origin in enumerate(ALLOWED_ORIGINS):
    output.append(f"  {i}: {repr(origin)}")

output.append("\n=== Middleware Configuration ===")
for mw in app.user_middleware:
    output.append(f"\nMiddleware: {mw.cls.__name__}")
    if hasattr(mw, 'kwargs') and mw.kwargs:
        for k, v in mw.kwargs.items():
            output.append(f"  {k}: {v}")
    if hasattr(mw, 'options') and mw.options:
        for k, v in mw.options.items():
            output.append(f"  {k}: {v}")

with open("cors_debug_output.txt", "w") as f:
    f.write("\n".join(output))

print("Output written to cors_debug_output.txt")
