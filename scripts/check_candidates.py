import sys
import os
from sqlalchemy import text

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate

def check_candidates():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        # Find Acme Corp client
        client = db.query(Client).filter(Client.name == "Acme Corp").first()
        if not client:
            print("ERROR: 'Acme Corp' client not found!")
            return

        print(f"Found Client: {client.name} (ID: {client.id})")
        
        # Count candidates
        count = db.query(Candidate).filter(Candidate.client_id == client.id).count()
        print(f"Total Candidates for {client.name}: {count}")
        
        if count > 0:
            candidates = db.query(Candidate).filter(Candidate.client_id == client.id).limit(5).all()
            print("\nFirst 5 Candidates:")
            for c in candidates:
                print(f"- {c.name} (Email: {c.email}, Status: {c.status})")
        else:
            print("\nNo candidates found. The Master Database view is empty because the database is empty.")

if __name__ == "__main__":
    check_candidates()
