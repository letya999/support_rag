"""
Test script for API metadata generation endpoint.

Tests that the /documents/metadata-generation/analyze endpoint
correctly processes qa_data.json and returns structured metadata.
"""

import asyncio
import json
import os
import sys
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()


async def test_analyze_endpoint():
    """Test the analyze endpoint with qa_data.json"""
    
    base_url = "http://localhost:8000"
    
    # Read qa_data.json
    qa_data_path = os.path.join('datasets', 'qa_data.json')
    with open(qa_data_path, 'rb') as f:
        file_content = f.read()
    
    print(f"📤 Uploading {qa_data_path} to /documents/metadata-generation/analyze...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{base_url}/documents/metadata-generation/analyze",
                files={"file": ("qa_data.json", file_content, "application/json")}
            )
            
            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                return
            
            result = response.json()
            
            print(f"\n✅ Analysis successful!")
            print(f"   Analysis ID: {result.get('analysis_id')}")
            print(f"   Total items: {result.get('total_items')}")
            print(f"   High confidence: {result.get('high_confidence')}")
            print(f"   Low confidence: {result.get('low_confidence')}")
            
            print(f"\n📊 Discovered Categories:")
            for cat in result.get('discovered_categories', []):
                print(f"   - {cat['name']}: {cat['question_count']} questions")
            
            print(f"\n📋 Q&A Pairs with Metadata (first 3):")
            for qa in result.get('qa_pairs', [])[:3]:
                print(f"\n   Q{qa['qa_index']+1}: {qa['question'][:50]}...")
                print(f"      Category: {qa['metadata']['category']}")
                print(f"      Intent: {qa['metadata']['intent']}")
                print(f"      Handoff: {qa['metadata']['requires_handoff']}")
            
            # Compare with expected
            expected_path = os.path.join('datasets', 'qa_data_extended.json')
            if os.path.exists(expected_path):
                with open(expected_path, 'r', encoding='utf-8') as f:
                    expected = json.load(f)
                
                print(f"\n🎯 Comparison with expected:")
                matches = 0
                for qa, exp in zip(result.get('qa_pairs', []), expected):
                    if qa['metadata']['category'] == exp['metadata']['category']:
                        matches += 1
                print(f"   Category match: {matches}/{len(expected)}")
                
        except httpx.ConnectError:
            print("❌ Connection error. Is the API server running?")
            print("   Run: uvicorn app.main:app --reload")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_analyze_endpoint())
