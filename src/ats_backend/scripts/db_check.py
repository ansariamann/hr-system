import sys
import os
import logging
from pprint import pprint

# Set up logging to stdout
logging.basicConfig(level=logging.ERROR)

from ats_backend.core.database import db_manager, Base
from ats_backend.models.activity_log import ActivityLog

# Ensure all models are imported so Base.metadata knows about them
import ats_backend.models

def check_and_create():
    try:
        db_manager.initialize()
        print("Creating missing tables...")
        # Since Base metadata has ActivityLog, this will create it if missing
        Base.metadata.create_all(bind=db_manager.engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_and_create()
