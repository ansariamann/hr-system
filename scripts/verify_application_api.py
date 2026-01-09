
import sys
import os
import requests
from uuid import uuid4
from datetime import timedelta

# Set env vars for DB connection
os.environ["POSTGRES_PASSWORD"] = "change_me_in_production"
os.environ["POSTGRES_HOST"] = "127.0.0.1"

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from ats_backend.core.database import db_manager
from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.models.candidate import Candidate
from ats_backend.models.application import Application
from ats_backend.auth.utils import create_access_token, get_password_hash

from ats_backend.core.config import settings

def verify_api():
    print(f"Connecting to DB: {settings.postgres_user}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    # Partial mask password
    pwd = settings.postgres_password
    print(f"Password len: {len(pwd)}")
    
    db_manager.initialize()
    with db_manager.get_session() as db:
        try:
            # 1. Ensure Client
            client = db.query(Client).filter(Client.name == "Test Client").first()
            if not client:
                client = Client(
                    id=uuid4(),
                    name="Test Client",
                    email_domain="test.com",
                    schema_name="public"
                )
                db.add(client)
                db.commit()
                print("Created Test Client")
            
            # 2. Ensure User
            user = db.query(User).filter(User.email == "test@test.com").first()
            if not user:
                user = User(
                    id=uuid4(),
                    email="test@test.com",
                    hashed_password=get_password_hash("password123"),
                    full_name="Test User",
                    role="admin",
                    client_id=client.id,
                    is_active=True
                )
                db.add(user)
                db.commit()
                print("Created Test User")

            # 3. Ensure Candidate
            candidate = db.query(Candidate).filter(Candidate.email == "candidate@test.com").first()
            if not candidate:
                candidate = Candidate(
                    id=uuid4(),
                    client_id=client.id,
                    name="John Doe",
                    email="candidate@test.com",
                    status="ACTIVE"
                )
                db.add(candidate)
                db.commit()
                print("Created Test Candidate")

            # 4. Ensure Application
            application = db.query(Application).filter(Application.candidate_id == candidate.id).first()
            if not application:
                application = Application(
                    id=uuid4(),
                    client_id=client.id,
                    candidate_id=candidate.id,
                    status="RECEIVED"
                )
                db.add(application)
                db.commit()
                print("Created Test Application")

            # 5. Generate Token
            # Make sure we use the IDs from the DB objects
            token = create_access_token(
                data={"sub": str(user.id), "client_id": str(client.id), "email": user.email},
                expires_delta=timedelta(minutes=30)
            )
            
            # 6. Call API
            headers = {"Authorization": f"Bearer {token}"}
            print("Calling API...")
            response = requests.get("http://localhost:8000/applications", headers=headers)
            
            if response.status_code != 200:
                print(f"FAILED: Status {response.status_code}")
                try:
                    print(response.json())
                except:
                    print(response.text)
                return

            data = response.json()
            print(f"Got {len(data)} applications")
            
            found = False
            for app in data:
                if str(app['id']) == str(application.id):
                    found = True
                    if "candidate" in app and app["candidate"] is not None:
                        print("SUCCESS: Candidate data found in response")
                        print(f"Candidate Name: {app['candidate'].get('name')}")
                    else:
                        print("FAILED: Candidate data MISSING in response")
                        print(app)
                    break
            
            if not found:
                 print("Warning: Created application not found in list (maybe filter mismatch?)")
                 print(f"Created app ID: {application.id}")
                 if len(data) > 0:
                     print(f"First returned app: {data[0]}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    verify_api()
