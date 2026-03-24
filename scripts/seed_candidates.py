import os
import random
import sys
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.append(src_path)

from ats_backend.core.database import db_manager
from ats_backend.models.candidate import Candidate
from ats_backend.models.client import Client


FIRST_NAMES = [
    "Aarav", "Aisha", "Akash", "Amelia", "Anaya", "Arjun", "Charlotte", "Diya",
    "Ethan", "Harper", "Ishaan", "Kavya", "Liam", "Maya", "Noah", "Olivia",
    "Priya", "Rohan", "Sophia", "Vihaan", "Zara", "Aditya", "Anika", "Dev",
]

LAST_NAMES = [
    "Sharma", "Patel", "Reddy", "Gupta", "Singh", "Mehta", "Iyer", "Nair",
    "Kapoor", "Malhotra", "Verma", "Joshi", "Fernandes", "Khan", "Das", "Roy",
    "Brown", "Johnson", "Smith", "Williams", "Taylor", "Anderson", "Thomas",
]

COMPANIES = [
    "Acme Systems", "Northstar Labs", "BlueOrbit Tech", "Vertex AI", "Nimbus Cloud",
    "BrightPath Solutions", "Quantum Stack", "Skyline Digital", "IronPeak Data",
    "Meridian Works", "Pioneer Health", "Zenith Commerce",
]

ROLES = [
    "Software Engineer", "Senior Software Engineer", "Frontend Developer",
    "Backend Developer", "Full Stack Developer", "QA Engineer", "DevOps Engineer",
    "Product Manager", "UI Designer", "Data Analyst", "Recruitment Specialist",
    "Sales Executive", "Marketing Associate",
]

LOCATIONS = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata",
    "Ahmedabad", "Remote", "New York", "San Francisco", "Toronto",
]

SKILLS_POOL = [
    "Python", "FastAPI", "Django", "React", "TypeScript", "Java", "Spring",
    "PostgreSQL", "MySQL", "Docker", "Kubernetes", "AWS", "Azure", "Figma",
    "Sales", "Marketing", "Excel", "Power BI", "Node.js", "Redis",
]


def build_candidate(index: int, client_id):
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f"{first_name} {last_name}"
    role = random.choice(ROLES)
    company = random.choice(COMPANIES)
    years_exp = random.randint(1, 12)
    current_ctc = Decimal(str(round(random.uniform(3.0, 28.0), 2)))
    expected_ctc = current_ctc + Decimal(str(round(random.uniform(1.0, 8.0), 2)))
    skills = random.sample(SKILLS_POOL, k=random.randint(3, 6))
    location = random.choice(LOCATIONS)
    timestamp = datetime.now(UTC).replace(tzinfo=None)

    return Candidate(
        id=uuid4(),
        client_id=client_id,
        name=full_name,
        email=f"seed.candidate.{index:04d}@example.com",
        phone=f"+91-9{random.randint(100000000, 999999999)}",
        company=company,
        location=location,
        skills={"skills": skills},
        experience={"years": years_exp, "current_role": role},
        ctc_current=current_ctc,
        ctc_expected=expected_ctc,
        previous_employment=[
            {
                "company": company,
                "title": role,
                "start_date": f"{2018 + random.randint(0, 4)}-01-01",
                "end_date": "Present",
            }
        ],
        remark="Bulk-seeded candidate record",
        status="ACTIVE",
        created_at=timestamp,
        updated_at=timestamp,
    )


def seed_candidates():
    target_count = int(os.environ.get("SEED_TARGET_COUNT", "300"))
    target_client_name = os.environ.get("SEED_CLIENT_NAME", "Acme Corp")

    print("Initializing database connection...")
    db_manager.initialize()

    with db_manager.get_session() as db:
        client = db.query(Client).filter(Client.name == target_client_name).first()
        if not client:
            available_clients = [row.name for row in db.query(Client).order_by(Client.name).all()]
            print(f"ERROR: '{target_client_name}' client not found.")
            print(f"Available clients: {available_clients}")
            return

        existing_count = db.query(Candidate).filter(Candidate.client_id == client.id).count()
        print(f"Client: {client.name} ({client.id})")
        print(f"Existing candidates: {existing_count}")
        print(f"Target candidates: {target_count}")

        if existing_count >= target_count:
            print("No seeding needed. Target already met.")
            return

        next_index = 1
        created_count = 0

        while existing_count + created_count < target_count:
            candidate_index = next_index
            email = f"seed.candidate.{candidate_index:04d}@example.com"
            next_index += 1
            exists = db.query(Candidate).filter(
                Candidate.client_id == client.id,
                Candidate.email == email,
            ).first()
            if exists:
                continue

            db.add(build_candidate(candidate_index, client.id))
            created_count += 1

            if created_count % 50 == 0:
                db.flush()
                print(f"Created {created_count} candidates so far...")

        db.commit()
        final_count = db.query(Candidate).filter(Candidate.client_id == client.id).count()
        print(f"Successfully created {created_count} candidates.")
        print(f"Final candidate count for {client.name}: {final_count}")


if __name__ == "__main__":
    seed_candidates()
