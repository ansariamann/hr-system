"""Check if user exists in database."""
import sqlite3

db = sqlite3.connect("temp_dev.db")
cursor = db.cursor()

# Get all users
print("=== Users in Database ===")
cursor.execute("SELECT id, email, is_active FROM users")
users = cursor.fetchall()
for user in users:
    print(f"  ID: {user[0]}")
    print(f"  Email: {user[1]}")
    print(f"  Is Active: {user[2]}")
    print()

# Check for admin user specifically
print("=== Looking for admin@acmecorp.com ===")
cursor.execute("SELECT * FROM users WHERE email = ?", ("admin@acmecorp.com",))
admin = cursor.fetchone()
if admin:
    print(f"  Found: {admin}")
else:
    print("  NOT FOUND!")

db.close()
