import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def run_all_migrations():
    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    scripts_dir = os.path.dirname(__file__)
    migration_files = sorted([
        f for f in os.listdir(scripts_dir) 
        if f.startswith("migrate-") and f.endswith(".sql")
    ])

    if not migration_files:
        print("No migration files found.")
        return

    for file_name in migration_files:
        file_path = os.path.join(scripts_dir, file_name)
        try:
            print(f"Applying migration: {file_name}")
            with open(file_path, 'r') as f:
                sql = f.read()

            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            print(f"Migration {file_name} applied successfully!")
        except Exception as e:
            print(f"Error applying migration {file_name}: {e}")

if __name__ == "__main__":
    run_all_migrations()
