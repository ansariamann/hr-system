"""Seed candidate data into SQLite database with all supported attributes."""

import json
import sqlite3
import uuid
from datetime import datetime

DB_PATH = "temp_dev.db"
CLIENT_NAME = "Acme Corp"


def json_value(value):
    return json.dumps(value) if value is not None else None


def iso_now() -> str:
    return datetime.utcnow().isoformat()


SEED_CANDIDATES = [
    {
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1-555-101-1001",
        "company": "Nova Systems",
        "location": "New York",
        "present_address": "221 West 32nd Street, New York, NY",
        "permanent_address": "18 Pine Road, Albany, NY",
        "date_of_birth": "1993-04-12",
        "previous_employment": [
            {"company": "Nova Systems", "title": "Senior Python Developer", "start_date": "2022-04-01", "end_date": "Present"},
            {"company": "BrightWare", "title": "Software Engineer", "start_date": "2019-06-01", "end_date": "2022-03-15"},
        ],
        "key_skill": "Backend architecture and API design",
        "resume_file_path": "/uploads/alice-johnson-resume.pdf",
        "resume_url": "/uploads/alice-johnson-resume.pdf",
        "skills": {"skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"]},
        "experience": {"years": 6},
        "ctc_current": 1850000,
        "ctc_expected": 2200000,
        "total_experience_years": 6.5,
        "notice_period_days": 30,
        "source": "LINKEDIN",
        "linkedin_url": "https://www.linkedin.com/in/alice-johnson-tech",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Strong backend profile. Good system design round.",
    },
    {
        "name": "Bob Smith",
        "email": "bob@example.com",
        "phone": "+1-555-101-1002",
        "company": "CloudPeak",
        "location": "San Francisco",
        "present_address": "900 Market Street, San Francisco, CA",
        "permanent_address": "17 Lake View Ave, Sacramento, CA",
        "date_of_birth": "1990-09-08",
        "previous_employment": [
            {"company": "CloudPeak", "title": "Platform Engineer", "start_date": "2021-08-01", "end_date": "Present"},
            {"company": "ByteLoop", "title": "DevOps Engineer", "start_date": "2017-02-10", "end_date": "2021-07-20"},
        ],
        "key_skill": "Cloud operations and Kubernetes",
        "resume_file_path": "/uploads/bob-smith-resume.pdf",
        "resume_url": "/uploads/bob-smith-resume.pdf",
        "skills": {"skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Python"]},
        "experience": {"years": 8},
        "ctc_current": 2400000,
        "ctc_expected": 2800000,
        "total_experience_years": 8.2,
        "notice_period_days": 60,
        "source": "REFERRAL",
        "linkedin_url": "https://www.linkedin.com/in/bob-smith-platform",
        "selected_client_name": "Acme Corp",
        "status": "SELECTED",
        "is_blacklisted": 0,
        "is_direct_interview": 1,
        "remark": "Selected for platform modernization role.",
    },
    {
        "name": "Charlie Brown",
        "email": "charlie@example.com",
        "phone": "+1-555-101-1003",
        "company": "PixelForge",
        "location": "London",
        "present_address": "40 Camden High Street, London",
        "permanent_address": "14 Kingfisher Lane, Bristol",
        "date_of_birth": "1995-01-17",
        "previous_employment": [
            {"company": "PixelForge", "title": "Frontend Engineer", "start_date": "2023-01-01", "end_date": "Present"},
            {"company": "MotionLab", "title": "UI Developer", "start_date": "2020-05-01", "end_date": "2022-12-15"},
        ],
        "key_skill": "React UI engineering",
        "resume_file_path": "/uploads/charlie-brown-resume.pdf",
        "resume_url": "/uploads/charlie-brown-resume.pdf",
        "skills": {"skills": ["React", "TypeScript", "Figma", "Tailwind", "Node.js"]},
        "experience": {"years": 5},
        "ctc_current": 1450000,
        "ctc_expected": 1750000,
        "total_experience_years": 5.1,
        "notice_period_days": 45,
        "source": "CAREERS_PAGE",
        "linkedin_url": "https://www.linkedin.com/in/charlie-brown-ui",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Good UI craft. Needs deeper API integration exposure.",
    },
    {
        "name": "Diana Ross",
        "email": "diana@example.com",
        "phone": "+1-555-101-1004",
        "company": "DataSpring",
        "location": "Remote",
        "present_address": "Remote - Austin, TX",
        "permanent_address": "19 Cedar Point, Austin, TX",
        "date_of_birth": "1992-11-03",
        "previous_employment": [
            {"company": "DataSpring", "title": "Data Engineer", "start_date": "2022-03-01", "end_date": "Present"},
            {"company": "MetricHub", "title": "BI Engineer", "start_date": "2018-09-01", "end_date": "2022-02-10"},
        ],
        "key_skill": "SQL pipelines and analytics engineering",
        "resume_file_path": "/uploads/diana-ross-resume.pdf",
        "resume_url": "/uploads/diana-ross-resume.pdf",
        "skills": {"skills": ["SQL", "Python", "Airflow", "dbt", "PostgreSQL"]},
        "experience": {"years": 7},
        "ctc_current": 1950000,
        "ctc_expected": 2350000,
        "total_experience_years": 7.3,
        "notice_period_days": 30,
        "source": "NAUKRI",
        "linkedin_url": "https://www.linkedin.com/in/diana-ross-data",
        "status": "INTERVIEW_SCHEDULED",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Interview scheduled with data team on next Wednesday.",
    },
    {
        "name": "Evan Wright",
        "email": "evan@example.com",
        "phone": "+1-555-101-1005",
        "company": "BlueOrbit",
        "location": "Berlin",
        "present_address": "12 Mullerstrasse, Berlin",
        "permanent_address": "84 River Walk, Hamburg",
        "date_of_birth": "1989-06-22",
        "previous_employment": [
            {"company": "BlueOrbit", "title": "Engineering Manager", "start_date": "2021-11-01", "end_date": "Present"},
            {"company": "AppStack", "title": "Senior Java Engineer", "start_date": "2015-07-01", "end_date": "2021-10-20"},
        ],
        "key_skill": "Team leadership and Java backend delivery",
        "resume_file_path": "/uploads/evan-wright-resume.pdf",
        "resume_url": "/uploads/evan-wright-resume.pdf",
        "skills": {"skills": ["Java", "Spring", "SQL", "Docker", "Leadership"]},
        "experience": {"years": 10},
        "ctc_current": 3200000,
        "ctc_expected": 3600000,
        "total_experience_years": 10.4,
        "notice_period_days": 90,
        "source": "CONSULTANT",
        "linkedin_url": "https://www.linkedin.com/in/evan-wright-eng",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 1,
        "remark": "Senior profile. Comp expectations high but reasonable.",
    },
    {
        "name": "Fiona Green",
        "email": "fiona@example.com",
        "phone": "+1-555-101-1006",
        "company": "DesignMint",
        "location": "Toronto",
        "present_address": "66 Queen Street West, Toronto",
        "permanent_address": "21 North Bay Drive, Toronto",
        "date_of_birth": "1996-02-11",
        "previous_employment": [
            {"company": "DesignMint", "title": "Product Designer", "start_date": "2023-02-01", "end_date": "Present"},
            {"company": "WireCanvas", "title": "UX Designer", "start_date": "2020-08-01", "end_date": "2023-01-15"},
        ],
        "key_skill": "Design systems and product UX",
        "resume_file_path": "/uploads/fiona-green-resume.pdf",
        "resume_url": "/uploads/fiona-green-resume.pdf",
        "skills": {"skills": ["Figma", "Design Systems", "Research", "Prototyping"]},
        "experience": {"years": 4},
        "ctc_current": 1300000,
        "ctc_expected": 1550000,
        "total_experience_years": 4.4,
        "notice_period_days": 30,
        "source": "LINKEDIN",
        "linkedin_url": "https://www.linkedin.com/in/fiona-green-product",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Could fit product design openings.",
    },
    {
        "name": "George Harris",
        "email": "george@example.com",
        "phone": "+1-555-101-1007",
        "company": "FinAxis",
        "location": "Mumbai",
        "present_address": "BKC, Mumbai, Maharashtra",
        "permanent_address": "Dadar West, Mumbai, Maharashtra",
        "date_of_birth": "1991-12-30",
        "previous_employment": [
            {"company": "FinAxis", "title": "Full Stack Engineer", "start_date": "2022-07-01", "end_date": "Present"},
            {"company": "CoreLogic", "title": "Software Developer", "start_date": "2018-04-01", "end_date": "2022-06-25"},
        ],
        "key_skill": "Full stack delivery in financial systems",
        "resume_file_path": "/uploads/george-harris-resume.pdf",
        "resume_url": "/uploads/george-harris-resume.pdf",
        "skills": {"skills": ["Node.js", "React", "PostgreSQL", "TypeScript", "Docker"]},
        "experience": {"years": 7},
        "ctc_current": 1800000,
        "ctc_expected": 2150000,
        "total_experience_years": 7.0,
        "notice_period_days": 60,
        "source": "EMPLOYEE_REFERRAL",
        "linkedin_url": "https://www.linkedin.com/in/george-harris-stack",
        "selected_client_name": "Acme Corp",
        "status": "HIRED",
        "is_blacklisted": 0,
        "is_direct_interview": 1,
        "remark": "Joined successfully. Retain for future benchmark data.",
    },
    {
        "name": "Hannah Lee",
        "email": "hannah@example.com",
        "phone": "+1-555-101-1008",
        "company": "RetailPulse",
        "location": "Singapore",
        "present_address": "1 Raffles Place, Singapore",
        "permanent_address": "18 Bukit Timah Road, Singapore",
        "date_of_birth": "1994-07-14",
        "previous_employment": [
            {"company": "RetailPulse", "title": "Business Analyst", "start_date": "2021-10-01", "end_date": "Present"},
            {"company": "InsightIQ", "title": "Operations Analyst", "start_date": "2018-01-01", "end_date": "2021-09-10"},
        ],
        "key_skill": "Business analysis and stakeholder management",
        "resume_file_path": "/uploads/hannah-lee-resume.pdf",
        "resume_url": "/uploads/hannah-lee-resume.pdf",
        "skills": {"skills": ["SQL", "Excel", "Analytics", "Stakeholder Management"]},
        "experience": {"years": 6},
        "ctc_current": 1250000,
        "ctc_expected": 1500000,
        "total_experience_years": 6.1,
        "notice_period_days": 30,
        "source": "INDEED",
        "linkedin_url": "https://www.linkedin.com/in/hannah-lee-ba",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Cross-functional analyst profile.",
    },
    {
        "name": "Ivan Martinez",
        "email": "ivan@example.com",
        "phone": "+1-555-101-1009",
        "company": "SecureMesh",
        "location": "Remote",
        "present_address": "Remote - Madrid, Spain",
        "permanent_address": "18 Calle Norte, Madrid",
        "date_of_birth": "1988-05-19",
        "previous_employment": [
            {"company": "SecureMesh", "title": "Security Engineer", "start_date": "2020-06-01", "end_date": "Present"},
            {"company": "InfraWatch", "title": "Systems Engineer", "start_date": "2014-02-01", "end_date": "2020-05-20"},
        ],
        "key_skill": "Infrastructure security and compliance",
        "resume_file_path": "/uploads/ivan-martinez-resume.pdf",
        "resume_url": "/uploads/ivan-martinez-resume.pdf",
        "skills": {"skills": ["Security", "AWS", "Linux", "Python", "Compliance"]},
        "experience": {"years": 11},
        "ctc_current": 3100000,
        "ctc_expected": 3450000,
        "total_experience_years": 11.0,
        "notice_period_days": 60,
        "source": "LINKEDIN",
        "linkedin_url": "https://www.linkedin.com/in/ivan-martinez-sec",
        "status": "REJECTED",
        "is_blacklisted": 1,
        "is_direct_interview": 0,
        "remark": "Rejected due to role mismatch; blacklisted in legacy flow.",
    },
    {
        "name": "Julia Chen",
        "email": "julia@example.com",
        "phone": "+1-555-101-1010",
        "company": "HealthBridge",
        "location": "Bangalore",
        "present_address": "Indiranagar, Bangalore, Karnataka",
        "permanent_address": "Mysuru Road, Bangalore, Karnataka",
        "date_of_birth": "1997-03-28",
        "previous_employment": [
            {"company": "HealthBridge", "title": "QA Engineer", "start_date": "2023-04-01", "end_date": "Present"},
            {"company": "SoftTrail", "title": "Test Engineer", "start_date": "2020-07-01", "end_date": "2023-03-20"},
        ],
        "key_skill": "Automation testing and release QA",
        "resume_file_path": "/uploads/julia-chen-resume.pdf",
        "resume_url": "/uploads/julia-chen-resume.pdf",
        "skills": {"skills": ["Selenium", "Playwright", "API Testing", "SQL"]},
        "experience": {"years": 4},
        "ctc_current": 950000,
        "ctc_expected": 1200000,
        "total_experience_years": 4.0,
        "notice_period_days": 30,
        "source": "WALK_IN",
        "linkedin_url": "https://www.linkedin.com/in/julia-chen-qa",
        "status": "LEFT",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "Candidate withdrew after accepting another offer.",
    },
    {
        "name": "Karan Mehta",
        "email": "karan.mehta@example.com",
        "phone": "+91-98765-41001",
        "company": "ScaleGrid",
        "location": "Pune",
        "present_address": "Baner, Pune, Maharashtra",
        "permanent_address": "Navi Peth, Pune, Maharashtra",
        "date_of_birth": "1993-08-05",
        "previous_employment": [
            {"company": "ScaleGrid", "title": "Senior Full Stack Engineer", "start_date": "2021-01-01", "end_date": "Present"},
            {"company": "CodeHarbor", "title": "Software Engineer", "start_date": "2017-06-01", "end_date": "2020-12-15"},
        ],
        "key_skill": "React and Python full stack",
        "resume_file_path": "/uploads/karan-mehta-resume.pdf",
        "resume_url": "/uploads/karan-mehta-resume.pdf",
        "skills": {"skills": ["React", "TypeScript", "Python", "FastAPI", "PostgreSQL"]},
        "experience": {"years": 7},
        "ctc_current": 2100000,
        "ctc_expected": 2500000,
        "total_experience_years": 7.4,
        "notice_period_days": 45,
        "source": "INTERNAL_DATABASE",
        "linkedin_url": "https://www.linkedin.com/in/karan-mehta-fullstack",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "New seed candidate 1.",
    },
    {
        "name": "Laila Noor",
        "email": "laila.noor@example.com",
        "phone": "+91-98765-41002",
        "company": "InsightLoop",
        "location": "Hyderabad",
        "present_address": "Madhapur, Hyderabad, Telangana",
        "permanent_address": "Gachibowli, Hyderabad, Telangana",
        "date_of_birth": "1995-10-10",
        "previous_employment": [
            {"company": "InsightLoop", "title": "Data Analyst", "start_date": "2022-06-01", "end_date": "Present"},
            {"company": "VizWare", "title": "Reporting Analyst", "start_date": "2019-01-01", "end_date": "2022-05-10"},
        ],
        "key_skill": "BI dashboards and SQL storytelling",
        "resume_file_path": "/uploads/laila-noor-resume.pdf",
        "resume_url": "/uploads/laila-noor-resume.pdf",
        "skills": {"skills": ["SQL", "Power BI", "Python", "Excel"]},
        "experience": {"years": 5},
        "ctc_current": 1100000,
        "ctc_expected": 1400000,
        "total_experience_years": 5.2,
        "notice_period_days": 30,
        "source": "LINKEDIN",
        "linkedin_url": "https://www.linkedin.com/in/laila-noor-analytics",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "New seed candidate 2.",
    },
    {
        "name": "Mohit Arora",
        "email": "mohit.arora@example.com",
        "phone": "+91-98765-41003",
        "company": "CircuitLabs",
        "location": "Chennai",
        "present_address": "OMR, Chennai, Tamil Nadu",
        "permanent_address": "Anna Nagar, Chennai, Tamil Nadu",
        "date_of_birth": "1992-01-29",
        "previous_employment": [
            {"company": "CircuitLabs", "title": "Mobile Engineer", "start_date": "2021-04-01", "end_date": "Present"},
            {"company": "BlueBox Apps", "title": "Android Developer", "start_date": "2016-09-01", "end_date": "2021-03-15"},
        ],
        "key_skill": "Android and Kotlin delivery",
        "resume_file_path": "/uploads/mohit-arora-resume.pdf",
        "resume_url": "/uploads/mohit-arora-resume.pdf",
        "skills": {"skills": ["Kotlin", "Android", "Java", "Firebase"]},
        "experience": {"years": 8},
        "ctc_current": 1750000,
        "ctc_expected": 2100000,
        "total_experience_years": 8.0,
        "notice_period_days": 60,
        "source": "NAUKRI",
        "linkedin_url": "https://www.linkedin.com/in/mohit-arora-mobile",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 1,
        "remark": "New seed candidate 3.",
    },
    {
        "name": "Nisha Kapoor",
        "email": "nisha.kapoor@example.com",
        "phone": "+91-98765-41004",
        "company": "TalentEdge",
        "location": "Delhi",
        "present_address": "Saket, New Delhi",
        "permanent_address": "Pitampura, New Delhi",
        "date_of_birth": "1996-06-16",
        "previous_employment": [
            {"company": "TalentEdge", "title": "Recruitment Coordinator", "start_date": "2023-01-01", "end_date": "Present"},
            {"company": "HirePath", "title": "Talent Associate", "start_date": "2020-03-01", "end_date": "2022-12-10"},
        ],
        "key_skill": "Recruitment operations and coordination",
        "resume_file_path": "/uploads/nisha-kapoor-resume.pdf",
        "resume_url": "/uploads/nisha-kapoor-resume.pdf",
        "skills": {"skills": ["Recruitment", "Coordination", "Excel", "Communication"]},
        "experience": {"years": 4},
        "ctc_current": 800000,
        "ctc_expected": 1000000,
        "total_experience_years": 4.1,
        "notice_period_days": 30,
        "source": "REFERRAL",
        "linkedin_url": "https://www.linkedin.com/in/nisha-kapoor-ops",
        "status": "INACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 0,
        "remark": "New seed candidate 4.",
    },
    {
        "name": "Omar Sheikh",
        "email": "omar.sheikh@example.com",
        "phone": "+91-98765-41005",
        "company": "EdgeForge",
        "location": "Kolkata",
        "present_address": "Salt Lake, Kolkata, West Bengal",
        "permanent_address": "Howrah, West Bengal",
        "date_of_birth": "1990-12-01",
        "previous_employment": [
            {"company": "EdgeForge", "title": "ML Engineer", "start_date": "2022-02-01", "end_date": "Present"},
            {"company": "NeuroVista", "title": "Data Scientist", "start_date": "2017-04-01", "end_date": "2022-01-12"},
        ],
        "key_skill": "Machine learning and MLOps",
        "resume_file_path": "/uploads/omar-sheikh-resume.pdf",
        "resume_url": "/uploads/omar-sheikh-resume.pdf",
        "skills": {"skills": ["Python", "Machine Learning", "MLOps", "AWS", "SQL"]},
        "experience": {"years": 9},
        "ctc_current": 2600000,
        "ctc_expected": 3050000,
        "total_experience_years": 9.3,
        "notice_period_days": 60,
        "source": "GITHUB",
        "linkedin_url": "https://www.linkedin.com/in/omar-sheikh-ml",
        "status": "ACTIVE",
        "is_blacklisted": 0,
        "is_direct_interview": 1,
        "remark": "New seed candidate 5.",
    },
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clients WHERE name = ? LIMIT 1", (CLIENT_NAME,))
    client_row = cursor.fetchone()
    if not client_row:
        raise SystemExit(f"ERROR: '{CLIENT_NAME}' client not found in {DB_PATH}")

    client_id = client_row[0]

    cursor.execute(
        "SELECT id FROM users WHERE client_id = ? ORDER BY created_at ASC LIMIT 1",
        (client_id,),
    )
    user_row = cursor.fetchone()
    assigned_user_id = user_row[0] if user_row else None

    print(f"Using client_id: {client_id}")
    print(f"Assigned user_id: {assigned_user_id or 'None'}")

    created = 0
    updated = 0

    for entry in SEED_CANDIDATES:
        now = iso_now()
        payload = {
            "client_id": client_id,
            "name": entry["name"],
            "email": entry["email"],
            "phone": entry["phone"],
            "company": entry["company"],
            "location": entry["location"],
            "present_address": entry["present_address"],
            "permanent_address": entry["permanent_address"],
            "date_of_birth": entry["date_of_birth"],
            "previous_employment": json_value(entry["previous_employment"]),
            "key_skill": entry["key_skill"],
            "resume_file_path": entry["resume_file_path"],
            "resume_url": entry["resume_url"],
            "assigned_user_id": assigned_user_id,
            "skills": json_value(entry["skills"]),
            "experience": json_value(entry["experience"]),
            "ctc_current": entry["ctc_current"],
            "ctc_expected": entry["ctc_expected"],
            "total_experience_years": entry["total_experience_years"],
            "notice_period_days": entry["notice_period_days"],
            "source": entry["source"],
            "linkedin_url": entry["linkedin_url"],
            "selected_client_name": entry.get("selected_client_name"),
            "status": entry["status"],
            "is_blacklisted": entry["is_blacklisted"],
            "is_direct_interview": entry["is_direct_interview"],
            "remark": entry["remark"],
            "updated_at": now,
        }

        cursor.execute("SELECT id FROM candidates WHERE email = ?", (entry["email"],))
        existing = cursor.fetchone()

        if existing:
            payload["id"] = existing[0]
            cursor.execute(
                """
                UPDATE candidates
                SET client_id = :client_id,
                    name = :name,
                    email = :email,
                    phone = :phone,
                    company = :company,
                    location = :location,
                    present_address = :present_address,
                    permanent_address = :permanent_address,
                    date_of_birth = :date_of_birth,
                    previous_employment = :previous_employment,
                    key_skill = :key_skill,
                    resume_file_path = :resume_file_path,
                    resume_url = :resume_url,
                    assigned_user_id = :assigned_user_id,
                    skills = :skills,
                    experience = :experience,
                    ctc_current = :ctc_current,
                    ctc_expected = :ctc_expected,
                    total_experience_years = :total_experience_years,
                    notice_period_days = :notice_period_days,
                    source = :source,
                    linkedin_url = :linkedin_url,
                    selected_client_name = :selected_client_name,
                    status = :status,
                    is_blacklisted = :is_blacklisted,
                    is_direct_interview = :is_direct_interview,
                    remark = :remark,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                payload,
            )
            updated += 1
            action = "Updated"
        else:
            payload["id"] = str(uuid.uuid4())
            payload["created_at"] = now
            cursor.execute(
                """
                INSERT INTO candidates (
                    id, client_id, name, email, phone, company, location,
                    present_address, permanent_address, date_of_birth,
                    previous_employment, key_skill, resume_file_path, resume_url,
                    assigned_user_id, skills, experience, ctc_current, ctc_expected,
                    total_experience_years, notice_period_days, source, linkedin_url, selected_client_name,
                    status, is_blacklisted, is_direct_interview, remark, created_at, updated_at
                ) VALUES (
                    :id, :client_id, :name, :email, :phone, :company, :location,
                    :present_address, :permanent_address, :date_of_birth,
                    :previous_employment, :key_skill, :resume_file_path, :resume_url,
                    :assigned_user_id, :skills, :experience, :ctc_current, :ctc_expected,
                    :total_experience_years, :notice_period_days, :source, :linkedin_url, :selected_client_name,
                    :status, :is_blacklisted, :is_direct_interview, :remark, :created_at, :updated_at
                )
                """,
                payload,
            )
            created += 1
            action = "Created"

        print(
            f"{action}: {entry['name']} | {entry['company']} | {entry['location']} | "
            f"skills={len(entry['skills']['skills'])} | status={entry['status']}"
        )

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM candidates WHERE client_id = ?", (client_id,))
    total = cursor.fetchone()[0]

    print(f"\nCreated: {created}")
    print(f"Updated: {updated}")
    print(f"Total candidates for {CLIENT_NAME}: {total}")

    conn.close()


if __name__ == "__main__":
    main()
