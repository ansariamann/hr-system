import sys
import os
from sqlalchemy import text

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager

def migrate():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        print("Checking if location column exists...")
        try:
            # Check if column exists
            result = db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='candidates' AND column_name='location'"
            ))
            if result.scalar():
                print("Location column already exists.")
            else:
                print("Adding location column to candidates table...")
                db.execute(text("ALTER TABLE candidates ADD COLUMN location VARCHAR(255)"))
                db.commit()
                print("Column added successfully.")
        except Exception as e:
            print(f"Error during migration: {e}")
            db.rollback()

if __name__ == "__main__":
    migrate()
