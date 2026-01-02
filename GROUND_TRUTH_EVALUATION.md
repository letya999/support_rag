# Ground Truth Matching & Retrieval Evaluation

This document describes the Ground Truth Matching system for evaluating retrieval performance without LLM calls.

## Overview

Ground Truth Matching is a retrieval evaluation system that:
- Creates a dataset with ~30 paraphrased questions and their ground truth answers
- Evaluates retrieval performance using 3 metrics: **Hit Rate**, **MRR**, and **Exact Match**
- Logs metrics to Langfuse for tracking and analysis
- Requires no LLM calls during evaluation (deterministic & cost-free)

## Architecture

### 1. Ground Truth Dataset

**File:** `ground_truth_dataset.json`

Structure:
```json
[
  {
    "question": "paraphrased question",
    "expected_chunk_answer": "correct answer from original QA data",
    "original_question": "original question from qa_data.json"
  },
  ...
]
```

**Generation:** Uses simple heuristic paraphrasing (no LLM required)
- Each original Q&A pair generates 3-4 paraphrased variants
- All variants point to the same correct answer
- Total: ~30 test items from 10 original Q&A pairs

### 2. Evaluation Metrics

#### Hit Rate (Recall@K)
- **Definition:** % of queries where correct answer found in top-K results
- **Calculation:** 1 if found in top-K, 0 otherwise → average
- **Example:** If correct answer found in top-3 for 30/30 queries → Hit Rate = 1.0
- **Interpretation:** Measures retrieval coverage

#### MRR (Mean Reciprocal Rank)
- **Definition:** Average reciprocal position of correct answer
- **Calculation:**
  - Position 1 → 1.0
  - Position 2 → 0.5
  - Position 3 → 0.33
  - Not found → 0.0
- **Example:** Average across all queries
- **Interpretation:** Measures ranking quality (higher = better ranking)

#### Exact Match
- **Definition:** % of queries where top-1 result is correct
- **Calculation:** 1 if top-1 matches, 0 otherwise → average
- **Example:** If 26/30 queries have correct answer at position 1 → Exact Match = 0.867
- **Interpretation:** Measures top-1 accuracy

## Usage

### Step 1: Generate Ground Truth Dataset

```bash
python generate_ground_truth_dataset.py
```

This creates `ground_truth_dataset.json` with paraphrased questions.

**Output:**
```
✅ Ground truth dataset saved to ground_truth_dataset.json
📊 Total items: 30
```

### Step 2: Run Evaluation

#### Option A: Demo Mode (No Database Required)
```bash
python evaluate_ground_truth_demo.py
```

Shows evaluation with mock retrieval results. Useful for testing the pipeline.

**Output:**
```
📊 EVALUATION RESULTS (DEMO MODE)
============================================================
Total queries evaluated: 30

🎯 Hit Rate (Recall@3): 1.0000 (30/30)
📈 MRR (Mean Reciprocal Rank): 0.9278
✅ Exact Match (top-1): 0.8667 (26/30)
```

#### Option B: Real Evaluation (Database + Embeddings Required)

Prerequisites:
1. Set environment variables:
```bash
export OPENAI_API_KEY="your-key"
export DATABASE_URL="postgresql://user:password@localhost:5432/support_rag"
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
```

2. Ingest data into vector database:
```bash
python ingest.py
```

3. Run evaluation:
```bash
python evaluate_ground_truth.py
```

**Output:**
- `evaluation_results_YYYYMMDD_HHMMSS.json` - Detailed results
- Metrics logged to Langfuse if configured

## Understanding Results

### Example Results File

```json
{
  "run_name": "ground-truth-eval-20260102-082830",
  "timestamp": "2026-01-02T08:28:30.123456",
  "top_k": 3,
  "total_queries": 30,
  "aggregate_metrics": {
    "hit_rate": 1.0,
    "mrr": 0.9278,
    "exact_match": 0.8667
  },
  "detailed_results": [
    {
      "question": "Can I reset my password??",
      "hit_rate": 1,
      "mrr": 0.5,
      "exact_match": 0,
      "found_at_position": 2
    },
    ...
  ]
}
```

### Interpreting Scores

**Good Performance:**
- Hit Rate > 0.9 (>90% of queries find correct answer in top-3)
- MRR > 0.8 (correct answer usually in top 1-2 positions)
- Exact Match > 0.7 (>70% of queries have correct answer at top-1)

**Needs Improvement:**
- Hit Rate < 0.8 (>20% of queries missing correct answer)
- MRR < 0.6 (correct answer often ranked 3rd or lower)
- Exact Match < 0.5 (<50% top-1 accuracy)

## Langfuse Integration

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set:

1. **Dataset Creation:**
   - Ground truth items synced to Langfuse dataset: `ground-truth-retrieval-eval`
   - Each item contains question + expected answer

2. **Trace Logging:**
   - Each query creates a trace with:
     - Input: question
     - Output: retrieved chunks + metrics
     - Scores: hit_rate, mrr, exact_match

3. **Score Recording:**
   - Individual scores per trace
   - Aggregate scores per run
   - Enables trend analysis and monitoring

## Files Generated

| File | Purpose |
|------|---------|
| `ground_truth_dataset.json` | Paraphrased questions + ground truth answers |
| `evaluation_results_*.json` | Detailed evaluation results |
| `evaluate_ground_truth.py` | Real evaluation (requires DB + embeddings) |
| `evaluate_ground_truth_demo.py` | Demo evaluation (mock retrieval) |
| `generate_ground_truth_dataset.py` | Dataset generation script |

## Key Differences: Ground Truth vs Ragas Evaluation

| Aspect | Ground Truth | Ragas Evaluation |
|--------|-------------|-----------------|
| **Focus** | Retrieval only | Full RAG pipeline |
| **LLM Usage** | None (no calls) | Required (for metrics) |
| **Speed** | ~1-2 sec for 30 items | ~30 sec+ (API calls) |
| **Cost** | Free | $0.01-0.10+ |
| **Metrics** | Hit Rate, MRR, Exact Match | Context Precision, Context Recall, Faithfulness |
| **Deterministic** | Yes (reproducible) | No (LLM-dependent) |

## Extending the Evaluation

### Adding More Test Questions

Edit `ground_truth_dataset.json` to add custom paraphrased questions:

```json
{
  "question": "your custom question",
  "expected_chunk_answer": "the correct answer from qa_data.json",
  "original_question": "optional reference to original question"
}
```

### Changing Top-K

Modify evaluation scripts:

```python
# evaluate_ground_truth.py
await run_evaluation(top_k=5)  # Evaluate top-5 instead of top-3

# evaluate_ground_truth_demo.py
run_demo_evaluation(top_k=5)
```

### Custom Metrics

Add new metrics to `calculate_metrics()` function:

```python
def calculate_metrics(question, expected_answer, retrieved_chunks, top_k=3):
    # ... existing code ...
    metrics["custom_metric"] = your_calculation
    return metrics
```

## Troubleshooting

### OPENAI_API_KEY Error
Set environment variable:
```bash
export OPENAI_API_KEY="sk-..."
python ingest.py
```

### DATABASE_URL Connection Error
Check PostgreSQL is running:
```bash
psql -c "SELECT 1"
```

### Langfuse Connection Issues
If Langfuse is not available, evaluation still runs but metrics aren't logged to Langfuse. Check logs for specific error.

## Summary

Ground Truth Matching provides:
✅ Fast retrieval evaluation (no LLM calls)
✅ Reproducible results (deterministic)
✅ Cost-free metrics
✅ Clear performance insights
✅ Langfuse integration for monitoring
✅ Focuses on retrieval quality exclusively
