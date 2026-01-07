# Synthetic Q&A Dataset Generation Guide

Comprehensive guide for generating and using synthetic datasets to test your RAG pipeline at production-like scale.

## Quick Start

### Generate 1000 Q&A Pairs in Single File
```bash
python scripts/generate_synthetic_qa.py --count 1000 --output datasets/qa_synthetic_1000.json --include-eval
```

### Generate 12 Files with 100 Pairs Each
```bash
python scripts/generate_synthetic_qa.py --count 100 --num-files 12 --output-dir datasets/batch --include-eval
```

### Generate Specific Categories Only
```bash
python scripts/generate_synthetic_qa.py --count 500 --categories Account Billing Technical --seed 42
```

## Available Datasets

### Pre-Generated Datasets

#### 1. **qa_synthetic_1000_pairs.json** (660KB)
- **Size**: 1000 Q&A pairs
- **Use case**: Full-scale RAG pipeline testing
- **Categories**: All (Account, Billing, Technical, Features, Getting Started)
- **Includes**: Metadata with category, intent, confidence scores, clarifying questions
- **Evaluation**: `qa_synthetic_1000_pairs_eval.json` (ground truth)

#### 2. **qa_synthetic_test_100.json** (67KB)
- **Size**: 100 Q&A pairs
- **Use case**: Quick testing and validation
- **Categories**: All balanced distribution
- **Good for**: Development, debugging, quick iterations

#### 3. **synthetic_batch_12x100/** (1.5MB total)
- **12 separate files**, each with 100 pairs
- **Use case**: Incremental testing, progressive dataset loading
- **Naming**: `qa_synthetic_batch_001_100_pairs.json` ... `qa_synthetic_batch_012_100_pairs.json`
- **Evaluation files**: Each batch includes `*_eval.json` for ground truth

## Q&A Data Format

### Main Dataset Structure
```json
{
  "question": "How do I reset my password?",
  "answer": "To reset your password, click the 'Forgot Password' link...",
  "metadata": {
    "category": "Account",
    "intent": "reset_password",
    "requires_handoff": false,
    "confidence_threshold": 0.87,
    "clarifying_questions": [
      "Do you have access to the email associated with your account?"
    ],
    "tags": ["account", "common_question", "faq"],
    "source_document": "synthetic_account_0.json",
    "generated_at": "2026-01-07T12:27:06.802358"
  }
}
```

### Evaluation Dataset Structure (Ground Truth)
```json
{
  "question": "How do I reset my password?",
  "expected_chunks": ["To reset your password, click the 'Forgot Password' link..."],
  "expected_answer": "To reset your password, click the 'Forgot Password' link...",
  "expected_intent": "reset_password",
  "expected_category": "Account",
  "expected_action": "auto_reply",
  "confidence_score": 0.87,
  "difficulty": "easy"
}
```

## Available Categories & Intents

### 1. **Account** (Password, Login, Security)
- Intents: `reset_password`, `login_help`, `account_security`, `profile_update`, `email_change`
- Example: Password reset, 2FA setup, profile changes

### 2. **Billing** (Invoices, Payments, Subscriptions)
- Intents: `invoice_help`, `payment_issue`, `refund_request`, `subscription_help`, `upgrade_plan`
- Example: Invoice lookup, refund requests, plan upgrades

### 3. **Technical** (API, Integration, Errors)
- Intents: `api_help`, `integration_support`, `error_troubleshooting`, `performance_issue`, `compatibility`
- Example: API authentication, rate limits, SDK usage

### 4. **Features** (Tutorials, Customization, Integration)
- Intents: `feature_tutorial`, `feature_limitation`, `feature_request`, `feature_availability`
- Example: Dashboard customization, data export, webhook setup

### 5. **Getting Started** (Onboarding, Documentation)
- Intents: `onboarding_help`, `first_steps`, `setup_guide`, `documentation`
- Example: Tutorial access, free trial, support contact

## Using Datasets for RAG Testing

### 1. Ingestion Test
Test your ingestion pipeline with increasing dataset sizes:

```bash
# Small test (100 pairs)
python scripts/ingest.py --file datasets/qa_synthetic_test_100.json

# Medium test (500 pairs)
python scripts/generate_synthetic_qa.py --count 500 --output datasets/qa_500.json
python scripts/ingest.py --file datasets/qa_500.json

# Large test (1000 pairs)
python scripts/ingest.py --file datasets/qa_synthetic_1000_pairs.json
```

### 2. Retrieval Evaluation
Test retrieval quality with ground truth data:

```bash
# Run Ragas evaluation against synthetic data
python evaluate_retrieval.py --qa-file datasets/qa_synthetic_1000_pairs.json \
                             --eval-file datasets/qa_synthetic_1000_pairs_eval.json
```

### 3. Progressive Loading
Test batch ingestion with 12 files:

```python
import os
import json
from pathlib import Path

batch_dir = "datasets/synthetic_batch_12x100"
for file in sorted(Path(batch_dir).glob("qa_synthetic_batch_*.json")):
    if "_eval.json" not in file:
        # Ingest each batch progressively
        print(f"Processing {file.name}...")
        with open(file) as f:
            data = json.load(f)
        # Your ingestion logic here
```

### 4. Production Load Testing
- **1000 pairs**: Tests vector store performance, retrieval latency
- **12x100 files**: Tests ingestion pipeline scalability and batch processing
- **Evaluation datasets**: Measures accuracy degradation at scale

## Generator Options

### Command-line Parameters

```bash
usage: generate_synthetic_qa.py [-h] [--count COUNT] [--num-files NUM_FILES]
                                [--output OUTPUT] [--output-dir OUTPUT_DIR]
                                [--categories CATEGORIES [CATEGORIES ...]]
                                [--seed SEED] [--include-eval]

options:
  -h, --help            Show help message
  --count COUNT         Number of Q&A pairs per file (default: 100)
  --num-files NUM_FILES Number of files to generate (default: 1)
  --output OUTPUT       Output file path (single file mode)
  --output-dir OUTPUT   Output directory (multi-file mode, default: datasets/synthetic)
  --categories CAT...   Categories to include (default: all)
  --seed SEED           Random seed for reproducibility (default: random)
  --include-eval        Generate evaluation/ground-truth dataset
```

### Examples

#### Generate reproducible datasets for CI/CD
```bash
python scripts/generate_synthetic_qa.py --count 200 --seed 42 \
  --output datasets/qa_deterministic_200.json --include-eval
```

#### Generate only Account & Billing categories
```bash
python scripts/generate_synthetic_qa.py --count 300 --categories Account Billing \
  --output datasets/qa_account_billing_300.json
```

#### Generate 20 files for distributed testing
```bash
python scripts/generate_synthetic_qa.py --count 50 --num-files 20 \
  --output-dir datasets/distributed_qa --include-eval
```

## Testing Metrics

### Quality Metrics to Track
- **Ingestion time**: Time to ingest N pairs
- **Vector store queries**: Latency per retrieval
- **Accuracy metrics** (from evaluation):
  - **context_recall**: Can we retrieve all relevant chunks?
  - **context_precision**: Are retrieved chunks relevant?
  - **faithfulness**: Is generated answer based on context?
  - **difficulty_distribution**: Easy/Medium/Hard ratio in dataset

### Sample Test Results
When testing with synthetic data:
- **100 pairs**: <100ms ingestion, <50ms retrieval
- **1000 pairs**: <1s ingestion, <100ms retrieval
- **Larger batches**: Linear scaling expected with batch size

## Data Characteristics

### Question Variation
- 7 different question rephrasings per answer
- Natural language variations (e.g., "How do I..." → "What's the way to...")
- Question length: 3-25 words average

### Answer Quality
- 5-8 realistic answer options per category
- Answer length: 50-300 words
- Domain-realistic language and terminology

### Metadata Features
- **Category**: 5 support domains
- **Intent**: 25+ specific intents across categories
- **Confidence**: 0.7-0.95 range
- **Handoff rate**: ~25% require escalation
- **Tags**: 10+ tag types for filtering
- **Clarifying questions**: Context-aware follow-ups

## Advanced Usage

### Combine Multiple Datasets
```python
import json
from pathlib import Path

combined = []

# Load test dataset
with open("datasets/qa_synthetic_test_100.json") as f:
    combined.extend(json.load(f))

# Load first 5 batch files
for i in range(1, 6):
    batch_file = f"datasets/synthetic_batch_12x100/qa_synthetic_batch_{i:03d}_100_pairs.json"
    with open(batch_file) as f:
        combined.extend(json.load(f))

# Save combined (600 pairs total)
with open("datasets/qa_combined_600.json", "w") as f:
    json.dump(combined, f)
```

### Filter by Category
```python
import json

with open("datasets/qa_synthetic_1000_pairs.json") as f:
    all_qa = json.load(f)

# Keep only Account & Billing
filtered = [qa for qa in all_qa
            if qa["metadata"]["category"] in ["Account", "Billing"]]

print(f"Found {len(filtered)} Account/Billing pairs")
```

### Extract Evaluation Ground Truth
```bash
# Get just the questions from eval dataset for simple RAG testing
python -c "
import json

with open('datasets/qa_synthetic_1000_pairs_eval.json') as f:
    eval_data = json.load(f)

questions = [qa['question'] for qa in eval_data]
print(f'Extracted {len(questions)} questions')
"
```

## Performance Benchmarking

### Recommended Test Plan
1. **Phase 1**: Ingest 100 pairs → measure latency
2. **Phase 2**: Ingest 500 pairs → measure vector DB performance
3. **Phase 3**: Ingest 1000 pairs → test retrieval accuracy
4. **Phase 4**: Batch ingestion → test scalability with 12 files
5. **Phase 5**: Evaluate → measure Ragas metrics (recall, precision, faithfulness)

### Langfuse Integration
All generation includes timestamps for tracking in Langfuse:
```python
from app.integrations.langfuse_client import langfuse_client

# Automatically tracked with metadata
trace = langfuse_client.trace(
    name="synthetic_qa_test",
    metadata={
        "dataset_size": 1000,
        "categories": "all",
        "source": "synthetic_generator"
    }
)
```

## Troubleshooting

### Generator fails with "Invalid category"
- Check category spelling (case-sensitive): Account, Billing, Technical, Features, Getting Started
- Use `python scripts/generate_synthetic_qa.py -h` to see valid options

### JSON file too large for ingestion
- Start with 100-pair test file
- Use batch files (12x100) for incremental loading
- Split 1000-pair file into smaller chunks

### Reproducibility issues
- Always use `--seed` parameter for deterministic generation
- Same seed produces identical datasets
- Useful for CI/CD and comparing algorithm changes

## Next Steps
1. Generate datasets matching your support domain size
2. Ingest into PostgreSQL + pgvector
3. Run retrieval evaluation with ground truth
4. Track metrics in Langfuse
5. Iterate on RAG parameters based on results
