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

def seed_remaining_candidates():
    print("Initializing database connection...")
    db_manager.initialize()
    
    with db_manager.get_session() as db:
        # Find Acme Corp client or any client
        client = db.query(Client).filter(Client.name == "Acme Corp").first()
        if not client:
            client = db.query(Client).first()
            
        if not client:
            # Create a default client if none exists
            print("No client found. Creating 'Acme Corp'...")
            client = Client(id=uuid4(), name="Acme Corp", email_domain="acmecorp.com")
            db.add(client)
            db.commit()
            db.refresh(client)

        print(f"Seeding candidates for: {client.name} (ID: {client.id})")
        
        # Candidate Data Samples with Remarks
        skills_pool = ["Python", "React", "Java", "SQL", "Docker", "AWS", "Figma", "Sales", "Marketing", "TypeScript", "Go", "Rust", "TensorFlow"]
        locations = ["New York", "San Francisco", "London", "Remote", "Berlin", "Toronto", "Mumbai", "Singapore", "Austin"]
        remarks_pool = [
            "Strong candidate, excellent communication skills.",
            "Technical test was average, but great portfolio.",
            "Referral from internal employee.",
            "Willing to relocate immediately.",
            "Asking for salary above budget.",
            "Great cultural fit.",
            "Needs visa sponsorship.",
            None,
            "Impressed with system design knowledge."
        ]
        
        candidates_data = [
            {"name": "Frank Castle", "email": "frank@example.com", "role": "Security Engineer"},
            {"name": "Grace Hopper", "email": "grace@example.com", "role": "Senior Architect"},
            {"name": "Heidi Klum", "email": "heidi@example.com", "role": "Product Designer"},
            {"name": "Ivan Drago", "email": "ivan@example.com", "role": "DevOps Engineer"},
            {"name": "Judy Garland", "email": "judy@example.com", "role": "Frontend Developer"},
            {"name": "Karl Marx", "email": "karl@example.com", "role": "Data Analyst"},
            {"name": "Liam Neeson", "email": "liam@example.com", "role": "Backend Developer"},
            {"name": "Mia Wallace", "email": "mia@example.com", "role": "UX Researcher"},
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
            candidate_skills = random.sample(skills_pool, k=random.randint(3, 6))
            years_exp = random.randint(2, 20)
            remark = random.choice(remarks_pool)
            
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
                remark=remark,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(candidate)
            created_count += 1
            print(f"Created: {candidate.name} - Remark: {remark}")
        
        db.commit()
        print(f"\nSuccessfully seeded {created_count} candidates with remarks.")

if __name__ == "__main__":
    seed_remaining_candidates()
