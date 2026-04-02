import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager

def clear_candidates():
    print("Initializing database connection...")
    db_manager.initialize()

    with db_manager.get_session() as db:
        from ats_backend.models.fsm_transition_log import FSMTransitionLog
        from ats_backend.models.interview_record import InterviewRecord
        from ats_backend.models.application import Application
        from ats_backend.models.company_employee import CompanyEmployee
        from ats_backend.models.candidate import Candidate
        
        try:
            # Delete dependent tables first
            print("Deleting transition logs...")
            db.query(FSMTransitionLog).delete()
            print("Deleting interview records...")
            db.query(InterviewRecord).delete()
            print("Deleting applications...")
            db.query(Application).delete()
            print("Unlinking company employees...")
            db.query(CompanyEmployee).update({"candidate_id": None}, synchronize_session=False)
            
            # Finally, delete candidates
            print("Deleting candidates...")
            deleted_count = db.query(Candidate).delete()
            db.commit()
            print(f"Successfully deleted {deleted_count} candidates and their related data.")
        except Exception as e:
            db.rollback()
            print(f"Error clearing data: {e}")

if __name__ == "__main__":
    clear_candidates()
