"""Check SQLite database contents."""
import sqlite3

conn = sqlite3.connect('temp_dev.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Count records
for table in ['clients', 'users', 'candidates', 'applications']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} records")
    except Exception as e:
        print(f"{table}: Error - {e}")

# Show sample data
print("\n--- Clients ---")
cursor.execute("SELECT id, name FROM clients")
for row in cursor.fetchall():
    print(f"  {row[0][:8]}... | {row[1]}")

print("\n--- Users ---")
cursor.execute("SELECT id, email, full_name FROM users")
for row in cursor.fetchall():
    print(f"  {row[0][:8]}... | {row[1]} | {row[2]}")

print("\n--- Candidates (first 10) ---")
cursor.execute("SELECT id, name, email, status FROM candidates LIMIT 10")
for row in cursor.fetchall():
    print(f"  {row[0][:8]}... | {row[1]} | {row[2]} | {row[3]}")

conn.close()
print("\nDatabase check complete!")
