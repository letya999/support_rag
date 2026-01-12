"""
Test script for zero-shot classification endpoints
"""
import asyncio
import sys
from app.services.staging import staging_service
from app.services.taxonomy import TaxonomyService
from app.services.classification.zeroshot_service import (
    ZeroShotClassificationService, 
    CategoryIntent
)

async def test_zeroshot():
    print("=" * 60)
    print("Testing Zero-Shot Classification Service")
    print("=" * 60)
    
    # Test 1: Get all categories from DB
    print("\n[1] Fetching categories from database...")
    taxonomy_service = TaxonomyService()
    try:
        categories = await taxonomy_service.get_all_categories()
        print(f"✓ Found {len(categories)} categories:")
        for cat in categories[:5]:  # Show first 5
            print(f"  - {cat['name']} (id: {cat['id']})")
        
        if len(categories) > 5:
            print(f"  ... and {len(categories) - 5} more")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 2: Get intents for first category
    if categories:
        print(f"\n[2] Fetching intents for category '{categories[0]['name']}'...")
        try:
            intents = await taxonomy_service.get_intents_by_category(
                category_id=categories[0]['id']
            )
            print(f"✓ Found {len(intents)} intents:")
            for intent in intents[:5]:
                print(f"  - {intent['name']} (id: {intent['id']})")
            
            if len(intents) > 5:
                print(f"  ... and {len(intents) - 5} more")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Test 3: Create test taxonomy
    print("\n[3] Building taxonomy structure...")
    taxonomy = []
    try:
        for cat in categories[:3]:  # Use first 3 categories
            intents = await taxonomy_service.get_intents_by_category(
                category_id=cat['id']
            )
            if intents:
                taxonomy.append(CategoryIntent(
                    name=cat['name'],
                    intents=[i['name'] for i in intents[:5]]  # Max 5 intents per category
                ))
        
        print(f"✓ Built taxonomy with {len(taxonomy)} categories:")
        for cat in taxonomy:
            print(f"  - {cat.name}: {len(cat.intents)} intents")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Test 4: Create test chunks
    print("\n[4] Creating test chunks...")
    test_chunks = [
        {
            "chunk_id": "test_1",
            "question": "Как восстановить пароль от аккаунта?",
            "answer": "Test answer"
        },
        {
            "chunk_id": "test_2",
            "question": "Не работает оплата картой",
            "answer": "Test answer"
        },
        {
            "chunk_id": "test_3",
            "question": "Где посмотреть историю заказов?",
            "answer": "Test answer"
        }
    ]
    print(f"✓ Created {len(test_chunks)} test chunks")
    
    # Test 5: Classify chunks
    if taxonomy:
        print("\n[5] Classifying chunks with Zero-Shot service...")
        try:
            service = ZeroShotClassificationService()
            results = await service.classify_chunks(test_chunks, taxonomy)
            
            print(f"✓ Successfully classified {len(results)} chunks:\n")
            for res in results:
                # Find original question
                original = next((c for c in test_chunks if c['chunk_id'] == res.chunk_id), None)
                question = original['question'] if original else "Unknown"
                
                print(f"  Question: {question}")
                print(f"  → Category: {res.category}")
                print(f"  → Intent: {res.intent}")
                print(f"  → Confidence: {res.confidence:.2f}\n")
        except Exception as e:
            print(f"✗ Error during classification: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_zeroshot())
