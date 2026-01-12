import sys
import os
import asyncio
import json

# Adjust path to find 'app'
sys.path.append(r"c:\Users\User\a_projects\support_rag")

from app.services.document_processing import DocumentProcessingService

async def main():
    path = r"c:\Users\User\a_projects\support_rag\blokirovka_accounta.csv"
    try:
        print(f"Processing {path}...")
        pairs = await DocumentProcessingService.process_file(path)
        print(f"Extracted {len(pairs)} pairs.")
        
        if pairs:
            # Check the first pair for metadata quality
            p = pairs[0]
            print(f"Sample Question: {p.question}")
            print(f"Sample Answer: {p.answer[:50]}...")
            print(f"Metadata: {json.dumps(p.metadata, ensure_ascii=False)}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
