import sys
import os
from sqlalchemy import text

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager

def install_extension():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        print("Attempting to create pgcrypto extension...")
        try:
            db.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            db.commit()
            print("Extension created successfully.")
        except Exception as e:
            print(f"Error creating extension: {e}")
            db.rollback()

if __name__ == "__main__":
    install_extension()
