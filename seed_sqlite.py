"""Seed candidate data into SQLite database."""
import sqlite3
import uuid
from datetime import datetime
import json
import random

conn = sqlite3.connect('temp_dev.db')
cursor = conn.cursor()

# Get client ID
cursor.execute("SELECT id FROM clients WHERE name = 'Acme Corp' LIMIT 1")
result = cursor.fetchone()
if not result:
    print("ERROR: 'Acme Corp' client not found!")
    exit(1)

client_id = result[0]
print(f"Using client_id: {client_id}")

# Candidate data
skills_pool = ["Python", "React", "Java", "SQL", "Docker", "AWS", "Figma", "TypeScript", "Node.js", "PostgreSQL"]
locations = ["New York", "San Francisco", "London", "Remote", "Berlin", "Toronto", "Mumbai"]

candidates = [
    {"name": "Alice Johnson", "email": "alice@example.com"},
    {"name": "Bob Smith", "email": "bob@example.com"},
    {"name": "Charlie Brown", "email": "charlie@example.com"},
    {"name": "Diana Ross", "email": "diana@example.com"},
    {"name": "Evan Wright", "email": "evan@example.com"},
    {"name": "Fiona Green", "email": "fiona@example.com"},
    {"name": "George Harris", "email": "george@example.com"},
    {"name": "Hannah Lee", "email": "hannah@example.com"},
    {"name": "Ivan Martinez", "email": "ivan@example.com"},
    {"name": "Julia Chen", "email": "julia@example.com"},
]

now = datetime.utcnow().isoformat()

for c in candidates:
    # Check if exists
    cursor.execute("SELECT id FROM candidates WHERE email = ?", (c["email"],))
    if cursor.fetchone():
        print(f"Skipping {c['name']} (already exists)")
        continue
    
    # Generate random data
    skills = random.sample(skills_pool, k=random.randint(3, 6))
    years = random.randint(2, 12)
    location = random.choice(locations)
    
    candidate_id = str(uuid.uuid4())
    skills_json = json.dumps({"skills": skills})
    exp_json = json.dumps({"years": years})
    phone = f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    
    cursor.execute("""
        INSERT INTO candidates (id, client_id, name, email, phone, location, skills, experience, status, is_blacklisted, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (candidate_id, client_id, c["name"], c["email"], phone, location, skills_json, exp_json, "ACTIVE", 0, now, now))
    
    print(f"Created: {c['name']} | {location} | {years}y exp | {skills}")

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM candidates")
print(f"\nTotal candidates in database: {cursor.fetchone()[0]}")

conn.close()
print("Done!")
