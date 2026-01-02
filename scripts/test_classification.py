#!/usr/bin/env python3
"""Test script for classification node."""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.nodes.classification.classifier import get_classification_service
from app.dataset.loader import load_ground_truth_dataset


async def test_classification():
    """Test classification on ground truth dataset."""

    print("\n" + "="*60)
    print("🧪 CLASSIFICATION NODE TEST")
    print("="*60)

    # Load dataset
    try:
        dataset = load_ground_truth_dataset()
        print(f"✅ Loaded {len(dataset)} items from dataset")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return

    # Get classifier
    try:
        service = get_classification_service()
        print("✅ Classifier loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load classifier: {e}")
        return

    # Test on first N items
    test_size = min(10, len(dataset))
    results = []

    print(f"\n📊 Testing on {test_size} items...\n")

    for i, item in enumerate(dataset[:test_size], 1):
        question = item.question

        print(f"[{i}/{test_size}] {question[:60]}...", end=" ", flush=True)

        try:
            result = await service.classify_both(question)

            print(f"✓")
            print(f"  Intent: {result.intent} ({result.intent_confidence:.2f})")
            print(f"  Category: {result.category} ({result.category_confidence:.2f})")

            results.append({
                "question": question,
                "intent": result.intent,
                "intent_confidence": float(result.intent_confidence),
                "category": result.category,
                "category_confidence": float(result.category_confidence),
            })

        except Exception as e:
            print(f"❌ Error: {e}")
            continue

    # Summary
    print("\n" + "="*60)
    print("📈 SUMMARY")
    print("="*60)
    print(f"Successfully classified: {len(results)}/{test_size}")

    avg_intent_conf = sum(r["intent_confidence"] for r in results) / len(results) if results else 0
    avg_category_conf = sum(r["category_confidence"] for r in results) / len(results) if results else 0

    print(f"Avg Intent Confidence: {avg_intent_conf:.3f}")
    print(f"Avg Category Confidence: {avg_category_conf:.3f}")

    # Save results
    output_file = f"classification_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to {output_file}")


async def test_single_question(question: str):
    """Test classification on a single question."""

    print(f"\n🧪 Testing classification for: {question}")
    print("-" * 60)

    service = get_classification_service()
    result = await service.classify_both(question)

    print(f"Intent: {result.intent} (confidence: {result.intent_confidence:.3f})")
    print(f"Category: {result.category} (confidence: {result.category_confidence:.3f})")
    print(f"\nAll category scores:")
    for cat, score in sorted(result.all_category_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {score:.3f}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test single question
        question = " ".join(sys.argv[1:])
        asyncio.run(test_single_question(question))
    else:
        # Test full dataset
        asyncio.run(test_classification())
