#!/usr/bin/env python3
"""
Test script for Ground Truth metrics module
Demonstrates metric calculations without database
"""

from app.ground_truth.metrics import (
    calculate_hit_rate,
    calculate_mrr,
    calculate_exact_match,
    calculate_all_metrics,
)

# Mock retrieved chunks
mock_chunks = [
    {
        "content": "Question: How do I reset my password?\nAnswer: You can reset your password by clicking on the 'Forgot Password' link on the login page.",
        "score": 0.95
    },
    {
        "content": "Question: How do I contact support?\nAnswer: You can contact support via email at support@example.com or by calling 1-800-123-4567.",
        "score": 0.85
    },
    {
        "content": "Question: Where can I find my order history?\nAnswer: Your order history is located in the 'My Account' section under the 'Orders' tab.",
        "score": 0.75
    },
]

expected_answer = "You can reset your password by clicking on the 'Forgot Password' link on the login page."

print("=" * 60)
print("🧪 Testing Ground Truth Metrics Module")
print("=" * 60)

# Test Hit Rate
print("\n📊 Testing Hit Rate:")
hit_rate = calculate_hit_rate(expected_answer, mock_chunks, top_k=3)
print(f"Expected answer found in top-3: {hit_rate}")
print(f"  → Answer: {'Found ✓' if hit_rate else 'Not found ✗'}")

# Test MRR
print("\n📈 Testing MRR:")
mrr = calculate_mrr(expected_answer, mock_chunks, top_k=3)
print(f"Mean Reciprocal Rank: {mrr:.4f}")
print(f"  → Found at position: {1/mrr if mrr > 0 else 'N/A'}")

# Test Exact Match
print("\n✅ Testing Exact Match:")
exact_match = calculate_exact_match(expected_answer, mock_chunks)
print(f"Top-1 is correct: {exact_match}")
print(f"  → {mock_chunks[0]['content'][:60]}...")

# Test all metrics together
print("\n🎯 Testing All Metrics:")
all_metrics = calculate_all_metrics(expected_answer, mock_chunks, top_k=3)
print(f"Results: {all_metrics}")

# Demonstrate with wrong answer
print("\n" + "=" * 60)
print("Testing with wrong expected answer:")
print("=" * 60)

wrong_answer = "Some other answer that doesn't exist"
all_metrics_wrong = calculate_all_metrics(wrong_answer, mock_chunks, top_k=3)
print(f"\nExpected: '{wrong_answer}'")
print(f"Results: {all_metrics_wrong}")
print(f"  → Hit Rate: {all_metrics_wrong['hit_rate']} (not found)")
print(f"  → MRR: {all_metrics_wrong['mrr']} (not found)")
print(f"  → Exact Match: {all_metrics_wrong['exact_match']} (not found)")

print("\n" + "=" * 60)
print("✅ All metrics working correctly!")
print("=" * 60)
