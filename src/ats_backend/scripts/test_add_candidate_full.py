import sys
import os
import uuid
from sqlalchemy.orm import Session
from ats_backend.core.database import db_manager
from ats_backend.models.candidate import Candidate
from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.models.activity_log import ActivityLog
from ats_backend.services.candidate_service import CandidateService
from ats_backend.schemas.candidate import CandidateCreate

def test_add_candidate_full():
    db_manager.initialize()
    with db_manager.get_session() as db:
        # Get a client and user
        client = db.query(Client).first()
        if not client:
            print("No client found")
            return
        
        user = db.query(User).filter(User.client_id == client.id).first()
        if not user:
            print("No user found")
            return
            
        service = CandidateService()
        data = CandidateCreate(
            name="Test Full Candidate",
            email=f"test_{uuid.uuid4().hex[:6]}@example.com",
            phone="1234567890",
            status="ACTIVE"
        )
        
        try:
            print(f"Attempting to create candidate for client {client.id}...")
            # Simulate endpoint logic
            candidate = service.create_candidate(
                db=db,
                client_id=client.id,
                candidate_data=data,
                user_id=user.id
            )
            print(f"Candidate created in service: {candidate.id}")
            
            activity_log = ActivityLog(
                client_id=client.id,
                user_id=user.id,
                action_type="CANDIDATE_CREATED",
                entity_id=candidate.id,
                details={"name": candidate.name, "email": candidate.email, "source": "manual"}
            )
            db.add(activity_log)
            print("Activity log added to session")
            
            db.commit()
            print("COMMIT SUCCESSFUL")
        except Exception as e:
            print(f"FAILED")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_add_candidate_full()
