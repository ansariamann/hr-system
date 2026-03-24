from sqlalchemy import inspect
from ats_backend.core.database import db_manager
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate
from ats_backend.models.activity_log import ActivityLog

def check_tables():
    db_manager.initialize()
    inspector = inspect(db_manager.engine)
    tables = inspector.get_table_names()
    
    with open("schema_out.txt", "w") as f:
        f.write(f"Tables found: {tables}\n")
        
        for table in ["clients", "candidates", "activity_logs", "audit_logs"]:
            if table in tables:
                f.write(f"Table '{table}' exists.\n")
                columns = [c['name'] for c in inspector.get_columns(table)]
                f.write(f"Columns in '{table}': {columns}\n")
            else:
                f.write(f"Table '{table}' MISSING!\n")

if __name__ == "__main__":
    check_tables()
