"""
Test script for AutoClassificationPipeline.

Tests automatic classification of qa_data.json → qa_data_extended.json format.
CPU-first approach with minimal LLM usage.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from app.services.metadata_generation.auto_classifier import AutoClassificationPipeline
from app.services.metadata_generation.handoff_detector import HandoffDetector


async def main():
    # 1. Load qa_data.json
    qa_data_path = os.path.join('datasets', 'qa_data.json')
    if not os.path.exists(qa_data_path):
        print(f"❌ Error: {qa_data_path} not found.")
        return

    with open(qa_data_path, 'r', encoding='utf-8') as f:
        qa_pairs = json.load(f)

    print(f"✅ Loaded {len(qa_pairs)} Q&A pairs from {qa_data_path}")

    # 2. Initialize pipeline
    print("\n📦 Initializing AutoClassificationPipeline...")
    pipeline = AutoClassificationPipeline(
        embedding_model="all-MiniLM-L6-v2",  # Small, fast, CPU-friendly
        distance_threshold=0.7,  # Lower = more granular clusters
        confidence_threshold=0.65,
        llm_validation_threshold=0.4  # Only call LLM if very uncertain
    )
    
    handoff_detector = HandoffDetector()

    # 3. Classify
    print("\n🔍 Running classification pipeline...")
    results, categories = await pipeline.classify_batch(
        qa_pairs, 
        use_llm_validation=True
    )

    # 4. Get handoff detection
    print("\n🚨 Detecting handoff requirements...")
    handoff_results = handoff_detector.detect_batch(qa_pairs)

    # 5. Show discovered categories
    print("\n" + "="*60)
    print("📊 DISCOVERED CATEGORIES:")
    print("="*60)
    for cat in pipeline.get_category_summary():
        print(f"\n   📁 {cat['name']}")
        print(f"      Questions: {cat['question_count']}")
        print(f"      Keywords: {', '.join(cat['keywords'][:3])}")

    # 6. Build extended data
    extended_data = []
    for qa, clf_result, handoff in zip(qa_pairs, results, handoff_results):
        metadata = {
            "category": clf_result.category,
            "intent": clf_result.intent,
            "requires_handoff": handoff["requires_handoff"],
            "confidence_threshold": handoff["confidence_threshold"],
            "clarifying_questions": handoff["clarifying_questions"]
        }
        
        extended_data.append({
            "question": qa["question"],
            "answer": qa["answer"],
            "metadata": metadata
        })

    # 7. Compare with expected
    expected_path = os.path.join('datasets', 'qa_data_extended.json')
    if os.path.exists(expected_path):
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_data = json.load(f)
        
        print("\n" + "="*60)
        print("🎯 COMPARISON WITH EXPECTED (qa_data_extended.json):")
        print("="*60)
        
        category_matches = 0
        intent_matches = 0
        
        for i, (gen, exp) in enumerate(zip(extended_data, expected_data)):
            gen_cat = gen["metadata"]["category"]
            exp_cat = exp["metadata"]["category"]
            gen_intent = gen["metadata"]["intent"]
            exp_intent = exp["metadata"]["intent"]
            
            # Fuzzy category match (contains key words)
            cat_match = (
                gen_cat.lower() == exp_cat.lower() or
                any(w in gen_cat.lower() for w in exp_cat.lower().split())
            )
            intent_match = gen_intent == exp_intent
            
            if cat_match:
                category_matches += 1
            if intent_match:
                intent_matches += 1
            
            status = "✅" if (cat_match and intent_match) else ("⚠️" if cat_match or intent_match else "❌")
            
            print(f"\n{status} Q{i+1}: {gen['question'][:45]}...")
            print(f"   Category: {gen_cat:<25} | Expected: {exp_cat}")
            if not cat_match:
                print(f"             ↑ mismatch")
            print(f"   Intent:   {gen_intent:<25} | Expected: {exp_intent}")
            if not intent_match:
                print(f"             ↑ mismatch")
        
        total = len(extended_data)
        print("\n" + "="*60)
        print(f"📈 RESULTS:")
        print(f"   Category Match: {category_matches}/{total} ({category_matches/total*100:.0f}%)")
        print(f"   Intent Match:   {intent_matches}/{total} ({intent_matches/total*100:.0f}%)")
        print("="*60)

    # 8. Save result
    output_path = os.path.join('datasets', 'qa_data_generated_check.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extended_data, f, indent=4, ensure_ascii=False)
    print(f"\n💾 Result saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
