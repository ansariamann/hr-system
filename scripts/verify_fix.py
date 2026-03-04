import sys
import os
import time
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

try:
    from ats_backend.core.database import db_manager
    from ats_backend.models.client import Client
    from ats_backend.models.candidate import Candidate
    from ats_backend.models.application import Application
    from ats_backend.services.application_service import ApplicationService
    from ats_backend.core.config import settings
except ImportError:
    print("Dependencies not available. Skipping execution.")
    sys.exit(0)

def verify_fix():
    print("Setting up verification scenario...")
    db_manager.initialize()

    with db_manager.get_session() as db:
        # Create Client
        client_id = uuid4()
        client = Client(id=client_id, name="Benchmark Client", email_domain="benchmark.com")
        db.add(client)

        # Create Candidate
        candidate_id = uuid4()
        candidate = Candidate(id=candidate_id, client_id=client_id, name="Benchmark Candidate")
        db.add(candidate)

        db.commit()

        print("Creating 150 applications...")
        # Create 150 applications to exceed the default limit of 100
        apps = []
        for i in range(150):
            app = Application(
                client_id=client_id,
                candidate_id=candidate_id,
                status="RECEIVED" if i < 50 else "SCREENING" if i < 100 else "INTERVIEW_SCHEDULED"
            )
            apps.append(app)

        db.add_all(apps)
        db.commit()

        service = ApplicationService()

        print("Benchmarking get_application_statistics...")
        start_time = time.time()
        stats = service.get_application_statistics(db, client_id)
        end_time = time.time()

        duration = end_time - start_time
        print(f"Time taken: {duration:.4f} seconds")
        print("Stats retrieved:", stats)

        # Check for functional bug fix
        active_count = stats.get("active_applications", 0)
        print(f"Active applications count: {active_count}")

        if active_count == 150:
            print("SUCCESS: Active applications count is correct (150). The limit bug is fixed.")
        elif active_count == 100:
            print("FAILURE: Active applications count is still capped at 100!")
        else:
            print(f"Unexpected count: {active_count}")

if __name__ == "__main__":
    verify_fix()
