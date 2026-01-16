from sqlalchemy import create_engine, text
import os

# Database connection parameters
DB_USER = os.getenv("POSTGRES_USER", "ats_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me_in_production")
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = os.getenv("POSTGRES_DB", "ats_db")

# Create connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def add_remark_column():
    """Add remark column to candidates table."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # Check if column exists first
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='candidates' AND column_name='remark';
            """)
            result = connection.execute(check_query)
            if result.fetchone():
                print("Column 'remark' already exists in 'candidates' table.")
            else:
                # Add the column
                alter_query = text("ALTER TABLE candidates ADD COLUMN remark TEXT;")
                connection.execute(alter_query)
                connection.commit()
                print("Successfully added 'remark' column to 'candidates' table.")

    except Exception as e:
        print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_remark_column()
