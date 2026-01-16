
from ats_backend.core.config import settings
import psycopg2

print(f"Connecting to: host={settings.postgres_host} port={settings.postgres_port} user={settings.postgres_user} db={settings.postgres_db}")

try:
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password
    )
    print("SUCCESS: Connected to database.")
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print(cur.fetchone())
    conn.close()
except Exception as e:
    print(f"FAILURE: {e}")
