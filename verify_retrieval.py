import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"

def test_search(query):
    print(f"\nSearching for: '{query}'")
    try:
        response = requests.get(f"{BASE_URL}/search", params={"q": query})
        if response.status_code == 200:
            data = response.json()
            print(f"Query: {data['query']}")
            print("Results:")
            for i, res in enumerate(data['results']):
                print(f"{i+1}. Score: {res['score']:.4f}")
                print(f"   Content: {res['content']}\n")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Test cases
    queries = [
        "How can I change my password?",
        "Do you ship to Europe?",
        "What cards do you accept?"
    ]
    
    for q in queries:
        test_search(q)
