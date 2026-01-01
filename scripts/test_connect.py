
import json
import os
import random
import time
import psycopg
from pgvector.psycopg import register_vector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "support_rag")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Mock embedding function (1536 dimensions for compatibility with OpenAI)
def get_mock_embedding():
    return [random.uniform(-1, 1) for _ in range(1536)]

def main():
    conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    print(f"Connecting to database: {DB_NAME} at {DB_HOST}:{DB_PORT}...")
    
    try:
        # Connect to the database
        with psycopg.connect(conn_str) as conn:
            # Register pgvector type
            register_vector(conn)
            
            with conn.cursor() as cur:
                # Check if ready
                cur.execute("SELECT 1")
                print("Database connection successful!")
                
                # Check if table exists
                cur.execute("SELECT to_regclass('public.documents')")
                if not cur.fetchone()[0]:
                    print("Table 'documents' does not exist. Please check initialization.")
                    return

                # Load Q&A data
                # Determine the absolute path to qa_data.json (assumed to be in the project root)
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(script_dir)
                qa_data_path = os.path.join(project_root, "qa_data.json")
                
                with open(qa_data_path, "r") as f:
                    qa_data = json.load(f)
                
                print(f"Loaded {len(qa_data)} Q&A pairs from qa_data.json")

                # Insert data
                print("Inserting data with mock embeddings...")
                for item in qa_data:
                    content = f"Q: {item['question']}\nA: {item['answer']}"
                    embedding = get_mock_embedding()
                    
                    cur.execute(
                        "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
                        (content, embedding)
                    )
                
                print("Data inserted successfully.")
                
                # Verify search
                print("Testing vector search...")
                search_vector = get_mock_embedding()
                cur.execute(
                    "SELECT id, content, embedding <=> %s AS distance FROM documents ORDER BY distance LIMIT 1",
                    (search_vector,)
                )
                
                result = cur.fetchone()
                if result:
                    print("\nSearch result (nearest neighbor):")
                    print(f"ID: {result[0]}")
                    print(f"Distance: {result[2]}")
                    print(f"Content: {result[1][:100]}...") # Truncate content for display
                else:
                    print("No results found.")
            
            # Commit changes
            conn.commit()
            print("\nTest completed successfully!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
