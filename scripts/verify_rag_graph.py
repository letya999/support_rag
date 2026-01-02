import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from app.rag_graph import rag_graph

load_dotenv()

async def main():
    print("Testing RAG Graph...")
    question = "Как мне сбросить пароль?"
    print(f"Question: {question}")
    
    try:
        # We can pass an empty config or specific callback if we entered here
        result = await rag_graph.ainvoke({"question": question})
        
        print("\n--- Answer ---")
        print(result["answer"])
        print("\n--- Context Docs ---")
        for i, doc in enumerate(result["docs"]):
            print(f"{i+1}. {doc[:100]}...")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
