# Ground Truth Matching & Retrieval Evaluation

Modular system for evaluating retrieval performance without LLM calls.

## Architecture

```
app/ground_truth/
├── __init__.py                  # Module exports
├── metrics.py                   # Individual metric functions
├── dataset_sync.py              # Langfuse dataset synchronization
├── evaluator.py                 # Main evaluation logic
└── rag_integration.py           # LangGraph integration
```

## Components

### 1. **metrics.py** - Metric Calculations

Individual functions for each metric:

- `calculate_hit_rate()` - Recall@K
- `calculate_mrr()` - Mean Reciprocal Rank
- `calculate_exact_match()` - Top-1 accuracy
- `calculate_all_metrics()` - All metrics at once

```python
from app.ground_truth.metrics import calculate_all_metrics

metrics = calculate_all_metrics(
    expected_answer="correct answer",
    retrieved_chunks=[{"content": "..."}, ...],
    top_k=3
)
# Returns: {"hit_rate": 1, "mrr": 1.0, "exact_match": 1}
```

### 2. **dataset_sync.py** - Langfuse Integration

Dataset management:

- `load_ground_truth_dataset()` - Load from JSON
- `sync_dataset_to_langfuse()` - Create/update in Langfuse
- `get_dataset_from_langfuse()` - Retrieve from Langfuse

```python
from app.ground_truth.dataset_sync import sync_dataset_to_langfuse
from langfuse import Langfuse

langfuse = Langfuse()
data = load_ground_truth_dataset("ground_truth_dataset.json")
sync_dataset_to_langfuse(langfuse, data)
```

### 3. **evaluator.py** - Main Evaluation

Complete evaluation workflow:

- Loads ground truth dataset
- Evaluates each question via `search_documents()`
- Calculates all metrics
- Logs to Langfuse (optional)
- Returns aggregate results

```python
from app.ground_truth.evaluator import evaluate_ground_truth
from langfuse import Langfuse

results = await evaluate_ground_truth(
    langfuse_client=Langfuse(),
    ground_truth_file="ground_truth_dataset.json",
    top_k=3
)

print(results["aggregate_metrics"])
# {
#   "hit_rate": 0.70,
#   "mrr": 0.63,
#   "exact_match": 0.57
# }
```

### 4. **rag_integration.py** - LangGraph Node

Integration with LangGraph workflows:

#### As a Separate Node

```python
from app.ground_truth.rag_integration import evaluation_node
from langfuse import Langfuse

workflow.add_node(
    "ground_truth_eval",
    lambda state: evaluation_node(
        state,
        langfuse_client=Langfuse(),
        top_k=3
    )
)

# Connect after retrieval
workflow.add_edge("retrieval_node", "ground_truth_eval")
```

#### Log Metrics to Existing Trace

```python
from app.ground_truth.rag_integration import log_metrics_to_trace
from app.ground_truth.metrics import calculate_all_metrics

# In any node, after retrieval
metrics = calculate_all_metrics(
    expected_answer=item["expected_chunk_answer"],
    retrieved_chunks=retrieved_chunks,
    top_k=3
)

log_metrics_to_trace(
    langfuse_client=langfuse,
    trace_id=state["trace_id"],
    metrics=metrics,
    found_at_position=position
)
```

## Usage

### 1. Command Line Evaluation

```bash
python evaluate_ground_truth.py
```

Evaluates the entire `ground_truth_dataset.json` and logs metrics to Langfuse.

**Output:**
```
📊 EVALUATION SUMMARY
============================================================
Run: ground-truth-eval-20260102-082945
Queries: 30/30

🎯 Hit Rate@3: 0.7000 (21/30)
📈 MRR: 0.6278
✅ Exact Match: 0.5667 (17/30)
============================================================

💾 Results saved: evaluation_results_20260102_082945.json
```

### 2. In LangGraph Workflow

Evaluate retrieval after any node:

```python
from langchain_core.messages import BaseMessage
from app.ground_truth import evaluate_ground_truth

async def retrieval_with_eval(state):
    # Perform retrieval
    results = await search_documents(embedding, top_k=3)

    # Optionally evaluate
    if should_evaluate:
        eval_results = await evaluate_ground_truth(
            langfuse_client=state.get("langfuse"),
            top_k=3
        )
        state["metrics"] = eval_results["aggregate_metrics"]

    return state
```

### 3. Programmatic Usage

```python
from app.ground_truth.metrics import calculate_hit_rate, calculate_mrr

# For a single question
expected = "correct answer"
chunks = [
    {"content": "Question: X\nAnswer: correct answer"},
    {"content": "..."}
]

hit_rate = calculate_hit_rate(expected, chunks, top_k=3)
mrr = calculate_mrr(expected, chunks, top_k=3)

print(f"Hit: {hit_rate}, MRR: {mrr:.2f}")
```

## Ground Truth Dataset Format

File: `ground_truth_dataset.json`

```json
[
  {
    "question": "How do I reset my password?",
    "expected_chunk_answer": "You can reset your password by clicking on the 'Forgot Password' link on the login page."
  },
  {
    "question": "I forgot my password, how do I recover it?",
    "expected_chunk_answer": "You can reset your password by clicking on the 'Forgot Password' link on the login page."
  },
  ...
]
```

- **30 test items** total
- **3-4 paraphrases** per original Q&A
- **Same correct answer** for all variants

## Metrics Explained

### Hit Rate (Recall@K)
**Definition:** % of queries where correct answer found in top-K results

**Calculation:**
```
1 if expected_answer found in any of top-K chunks
0 otherwise
Average across all queries
```

**Example:**
- 21 out of 30 queries found correct answer in top-3 → Hit Rate = 0.70

**Interpretation:**
- Measures retrieval coverage
- Higher is better (target: >0.9)

### MRR (Mean Reciprocal Rank)
**Definition:** Average reciprocal position of correct answer

**Calculation:**
```
Position 1 → 1.0
Position 2 → 0.5
Position 3 → 0.33
Not found → 0.0
Average across all queries
```

**Example:**
- Correct answers at positions: [1, 1, 2, 3, 1, ...] → Average MRR = 0.628

**Interpretation:**
- Measures ranking quality
- Higher is better (target: >0.8)
- Penalizes lower positions

### Exact Match (Top-1)
**Definition:** % of queries where top-1 result is correct

**Calculation:**
```
1 if top-1 chunk contains expected_answer
0 otherwise
Average across all queries
```

**Example:**
- 17 out of 30 top-1 results correct → Exact Match = 0.567

**Interpretation:**
- Measures top-1 accuracy
- Higher is better (target: >0.7)
- Most user-visible metric

## Example Results

```json
{
  "run_name": "ground-truth-eval-20260102-082945",
  "timestamp": "2026-01-02T08:29:45.123456",
  "top_k": 3,
  "total_queries": 30,
  "aggregate_metrics": {
    "hit_rate": 0.7,
    "mrr": 0.6278,
    "exact_match": 0.5667
  },
  "detailed_results": [
    {
      "question": "How do I reset my password?",
      "expected_answer": "You can reset your password...",
      "found_at_position": 1,
      "hit_rate": 1,
      "mrr": 1.0,
      "exact_match": 1
    },
    ...
  ]
}
```

## Langfuse Integration

When Langfuse is configured:

### Dataset
- Name: `ground-truth-retrieval-eval`
- Items: Ground truth Q&A pairs
- Auto-synced on first run

### Traces
- Each evaluation creates traces with:
  - Input: question
  - Output: retrieved chunks + metrics
  - Scores: hit_rate, mrr, exact_match

### Monitoring
- View metrics trends over time
- Compare runs
- Identify improvement opportunities

## Performance Characteristics

| Aspect | Value |
|--------|-------|
| Time for 30 queries | ~10-30 sec |
| Cost | Free (no LLM calls) |
| Deterministic | Yes |
| Requires DB | Yes (for real evaluation) |
| API calls | Only embeddings |

## Advanced Usage

### Custom Top-K Values

```python
# Evaluate at different K values
for top_k in [1, 3, 5, 10]:
    results = await evaluate_ground_truth(
        top_k=top_k
    )
    print(f"Top-{top_k}: Hit Rate = {results['aggregate_metrics']['hit_rate']}")
```

### Integration with Ragas

Use Ground Truth for quick retrieval checks, Ragas for full RAG evaluation:

```python
# Quick check - Ground Truth (free, fast)
gt_results = await evaluate_ground_truth()

# Full evaluation - Ragas (LLM-based, slower)
ragas_results = await ragas_evaluate()
```

### Custom Evaluation Function

Create specialized evaluator:

```python
async def custom_eval(ground_truth_file, custom_filter):
    data = load_ground_truth_dataset(ground_truth_file)
    filtered = [item for item in data if custom_filter(item)]

    results = await evaluate_ground_truth(
        ground_truth_data=filtered,
        top_k=3
    )
    return results
```

## Troubleshooting

### Import Errors
Ensure module is installed:
```bash
pip install -r requirements.txt
```

### Langfuse Connection Issues
If Langfuse unavailable, evaluation still runs but metrics aren't logged.

### No Results
Check:
- `ground_truth_dataset.json` exists
- Database is running (for real evaluation)
- `OPENAI_API_KEY` is set

## Summary

Ground Truth Matching provides:
✅ Modular metric calculations
✅ Langfuse dataset synchronization
✅ Complete evaluation workflow
✅ LangGraph integration ready
✅ No LLM calls (fast & free)
✅ Reproducible results
✅ Easy to extend
