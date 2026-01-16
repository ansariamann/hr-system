
import sys
import os
import uuid
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))

from ats_backend.core.config import settings
from ats_backend.models.candidate import Candidate
from ats_backend.services.candidate_service import CandidateService
from ats_backend.schemas.candidate import CandidateCreate

def run_verification():
    print("Starting Search Verification...")
    
    # Setup DB connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        service = CandidateService()
        
        # 1. Create a dummy client ID for testing isolation
        from ats_backend.models.client import Client
        test_client = Client(
            id=uuid.uuid4(),
            name="Test Client Corp",
            email_domain="test.com",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )
        db.add(test_client)
        db.commit()
        test_client_id = test_client.id
        print(f"Using Test Client ID: {test_client_id}")
        
        # 2. Create Test Candidates
        candidates_data = [
            {
                "name": "Alice Python",
                "email": f"alice_{uuid.uuid4()}@test.com",
                "skills": {"skills": ["Python", "Django"]},
                "status": "ACTIVE"
            },
            {
                "name": "Bob Java",
                "email": f"bob_{uuid.uuid4()}@test.com",
                "skills": {"skills": ["Java", "Spring"]},
                "status": "ACTIVE"
            },
            {
                "name": "Charlie Python",
                "email": f"charlie_{uuid.uuid4()}@test.com",
                "skills": {"skills": ["Python", "Flask"]},
                "status": "HIRED"
            }
        ]
        
        created_candidates = []
        for data in candidates_data:
            c = Candidate(
                id=uuid.uuid4(),
                client_id=test_client_id,
                name=data["name"],
                email=data["email"],
                skills=data["skills"],
                status=data["status"],
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            db.add(c)
            created_candidates.append(c)
        
        db.commit()
        print(f"Created {len(created_candidates)} test candidates.")
        
        # 3. Test Cases
        
        # Case A: Search by Name only
        results_name = service.search_candidates(db, test_client_id, name_pattern="Alice")
        print(f"Search Name 'Alice': Found {len(results_name)} (Expected 1)")
        if len(results_name) != 1 or results_name[0].name != "Alice Python":
            print("FAIL: Name search failed")
        
        # Case B: Search by Skill only
        results_skill = service.search_candidates(db, test_client_id, skills=["Python"])
        print(f"Search Skill 'Python': Found {len(results_skill)} (Expected 2)") # Alice and Charlie
        if len(results_skill) != 2:
            print("FAIL: Skill search failed")
            
        # Case C: Combined Name AND Skill
        results_combined = service.search_candidates(db, test_client_id, name_pattern="Alice", skills=["Python"])
        print(f"Search Name 'Alice' AND Skill 'Python': Found {len(results_combined)} (Expected 1)")
        if len(results_combined) != 1 or results_combined[0].name != "Alice Python":
            print("FAIL: Combined Name+Skill search failed")
            
        # Case D: Combined Name AND Skill (No Match)
        results_mismatch = service.search_candidates(db, test_client_id, name_pattern="Bob", skills=["Python"])
        print(f"Search Name 'Bob' AND Skill 'Python': Found {len(results_mismatch)} (Expected 0)")
        if len(results_mismatch) != 0:
            print("FAIL: Mismatch search returned results")
            
        # Case E: Combined Skill AND Status
        results_status = service.search_candidates(db, test_client_id, skills=["Python"], status="HIRED")
        print(f"Search Skill 'Python' AND Status 'HIRED': Found {len(results_status)} (Expected 1)") # Charlie only
        if len(results_status) != 1 or results_status[0].name != "Charlie Python":
             print("FAIL: Skill+Status search failed")
             
        # Cleanup
        print("Cleaning up test data...")
        for c in created_candidates:
            db.delete(c)
        db.delete(test_client)
        db.commit()
        print("Verification Complete.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
