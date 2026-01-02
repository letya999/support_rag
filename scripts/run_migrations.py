import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def run_migration(file_path):
    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    if not os.path.exists(file_path):
        print(f"Error: Migration file not found: {file_path}")
        return

    try:
        print(f"Applying migration: {file_path}")
        with open(file_path, 'r') as f:
            sql = f.read()

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("Migration applied successfully!")
    except Exception as e:
        print(f"Error applying migration: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        migration_file = os.path.join(os.path.dirname(__file__), sys.argv[1])
    else:
        migration_file = os.path.join(os.path.dirname(__file__), "migrate-001-add-metadata.sql")
    run_migration(migration_file)
