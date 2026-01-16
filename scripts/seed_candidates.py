import sys
import os
import random
from datetime import datetime
from uuid import uuid4

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate

def seed_candidates():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        # Find Acme Corp client
        client = db.query(Client).filter(Client.name == "Acme Corp").first()
        if not client:
            print("ERROR: 'Acme Corp' client not found! Run seed_admin.py first.")
            return

        print(f"Seeding candidates for: {client.name} (ID: {client.id})")
        
        # Candidate Data Samples
        skills_pool = ["Python", "React", "Java", "SQL", "Docker", "AWS", "Figma", "Sales", "Marketing", "TypeScript"]
        locations = ["New York", "San Francisco", "London", "Remote", "Berlin", "Toronto", "Mumbai"]
        
        candidates_data = [
            {"name": "Alice Johnson", "email": "alice@example.com", "role": "Senior Developer"},
            {"name": "Bob Smith", "email": "bob@example.com", "role": "Product Manager"},
            {"name": "Charlie Brown", "email": "charlie@example.com", "role": "Designer"},
            {"name": "Diana Ross", "email": "diana@example.com", "role": "Frontend Dev"},
            {"name": "Evan Wright", "email": "evan@example.com", "role": "Backend Dev"},
        ]
        
        created_count = 0
        
        for data in candidates_data:
            # Check if exists
            exists = db.query(Candidate).filter(
                Candidate.client_id == client.id,
                Candidate.email == data["email"]
            ).first()
            
            if exists:
                print(f"Skipping {data['name']} (already exists)")
                continue
                
            # Create Candidate
            candidate_skills = random.sample(skills_pool, k=random.randint(2, 5))
            years_exp = random.randint(1, 15)
            
            candidate = Candidate(
                id=uuid4(),
                client_id=client.id,
                name=data["name"],
                email=data["email"],
                phone=f"+1-555-01{random.randint(0,99):02d}",
                location=random.choice(locations),
                skills={"skills": candidate_skills},
                experience={"years": years_exp, "current_role": data["role"]},
                status="ACTIVE",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(candidate)
            created_count += 1
            print(f"Created: {candidate.name} - {candidate.location} - {years_exp} yrs - Skills: {candidate_skills}")
        
        db.commit()
        print(f"\nSuccessfully seeded {created_count} candidates.")

if __name__ == "__main__":
    seed_candidates()
