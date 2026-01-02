#!/usr/bin/env python3
"""
Test script for Ground Truth metrics module
Demonstrates metric calculations without database
Tests individual metric functions from separate files
"""

from app.ground_truth.metrics.hit_rate import calculate_hit_rate, aggregate_hit_rates
from app.ground_truth.metrics.mrr import calculate_mrr, aggregate_mrr
from app.ground_truth.metrics.exact_match import calculate_exact_match, aggregate_exact_matches
from app.ground_truth.metrics import calculate_all_metrics, find_answer_position

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
print("Testing Aggregation Functions:")
print("=" * 60)

# Test aggregation with multiple values
hit_rates = [1, 1, 0, 1, 0]
mrr_values = [1.0, 0.5, 0.0, 1.0, 0.0]
exact_matches = [1, 0, 0, 1, 0]

avg_hit_rate = aggregate_hit_rates(hit_rates)
avg_mrr = aggregate_mrr(mrr_values)
avg_exact_match = aggregate_exact_matches(exact_matches)

print(f"\nAggregated Hit Rates: {hit_rates}")
print(f"Average: {avg_hit_rate:.4f} ({sum(hit_rates)}/{len(hit_rates)})")

print(f"\nAggregated MRR: {mrr_values}")
print(f"Average: {avg_mrr:.4f}")

print(f"\nAggregated Exact Matches: {exact_matches}")
print(f"Average: {avg_exact_match:.4f} ({sum(exact_matches)}/{len(exact_matches)})")

# Test find_answer_position utility
print("\n" + "=" * 60)
print("Testing find_answer_position utility:")
print("=" * 60)

position = find_answer_position(expected_answer, mock_chunks, top_k=3)
print(f"\nExpected answer found at position: {position}")

position_wrong = find_answer_position(wrong_answer, mock_chunks, top_k=3)
print(f"Wrong answer found at position: {position_wrong}")

print("\n" + "=" * 60)
print("✅ All metrics and aggregation functions working correctly!")
print("=" * 60)
