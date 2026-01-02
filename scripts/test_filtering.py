#!/usr/bin/env python3
"""Test script for metadata filtering node."""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.nodes.metadata_filtering.filtering import get_metadata_filtering_service
from app.nodes.classification.classifier import get_classification_service
from app.dataset.loader import load_ground_truth_dataset


async def test_filtering():
    """Test metadata filtering with fallback mechanisms."""

    print("\n" + "="*60)
    print("🧪 METADATA FILTERING TEST")
    print("="*60)

    # Load dataset
    try:
        dataset = load_ground_truth_dataset()
        print(f"✅ Loaded {len(dataset)} items from dataset")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return

    # Get services
    try:
        classifier = get_classification_service()
        filter_service = get_metadata_filtering_service()
        print("✅ Services loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load services: {e}")
        return

    # Test on first N items
    test_size = min(10, len(dataset))
    results = []
    fallback_count = 0

    print(f"\n📊 Testing on {test_size} items...\n")

    for i, item in enumerate(dataset[:test_size], 1):
        question = item.question

        print(f"[{i}/{test_size}] {question[:50]}...", end=" ", flush=True)

        try:
            # First classify
            class_result = await classifier.classify_both(question)

            # Then filter
            filter_result = await filter_service.filter_and_search(
                question=question,
                category=class_result.category,
                category_confidence=class_result.category_confidence,
                top_k=3,
            )

            print(f"✓")
            print(f"  Category: {class_result.category} ({class_result.category_confidence:.2f})")
            print(f"  Filter used: {filter_result.filter_used}, Fallback: {filter_result.fallback_triggered}")
            print(f"  Docs found: {len(filter_result.docs)}")

            if filter_result.fallback_triggered:
                fallback_count += 1

            results.append({
                "question": question,
                "category": class_result.category,
                "category_confidence": float(class_result.category_confidence),
                "filter_used": filter_result.filter_used,
                "fallback_triggered": filter_result.fallback_triggered,
                "docs_count": len(filter_result.docs),
                "reason": filter_result.reason,
            })

        except Exception as e:
            print(f"❌ Error: {e}")
            continue

    # Summary
    print("\n" + "="*60)
    print("📈 SUMMARY")
    print("="*60)
    print(f"Successfully processed: {len(results)}/{test_size}")
    print(f"Filter used: {sum(1 for r in results if r['filter_used'])}/{len(results)}")
    print(f"Fallback triggered: {fallback_count}/{len(results)} ({fallback_count/len(results)*100:.1f}%)")

    avg_confidence = (
        sum(r["category_confidence"] for r in results) / len(results)
        if results
        else 0
    )
    print(f"Avg Category Confidence: {avg_confidence:.3f}")

    # Save results
    output_file = f"filtering_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to {output_file}")

    # Recommendations
    if fallback_count / len(results) > 0.3:
        print("\n⚠️  WARNING: Fallback triggered > 30% of the time")
        print("   Consider adjusting category confidence thresholds or adding more documents to categories")


async def test_single_question(question: str):
    """Test classification and filtering on a single question."""

    print(f"\n🧪 Testing: {question}")
    print("-" * 60)

    classifier = get_classification_service()
    filter_service = get_metadata_filtering_service()

    # Classify
    class_result = await classifier.classify_both(question)
    print(f"Classification:")
    print(f"  Intent: {class_result.intent} ({class_result.intent_confidence:.3f})")
    print(f"  Category: {class_result.category} ({class_result.category_confidence:.3f})")

    # Filter
    filter_result = await filter_service.filter_and_search(
        question=question,
        category=class_result.category,
        category_confidence=class_result.category_confidence,
        top_k=3,
    )

    print(f"\nFiltering:")
    print(f"  Filter used: {filter_result.filter_used}")
    print(f"  Fallback triggered: {filter_result.fallback_triggered}")
    print(f"  Reason: {filter_result.reason}")
    print(f"  Documents found: {len(filter_result.docs)}")

    if filter_result.docs:
        print(f"\nRetrieved documents:")
        for j, doc in enumerate(filter_result.docs, 1):
            print(f"  {j}. {doc[:100]}...")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test single question
        question = " ".join(sys.argv[1:])
        asyncio.run(test_single_question(question))
    else:
        # Test full dataset
        asyncio.run(test_filtering())
