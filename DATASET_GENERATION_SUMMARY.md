# Synthetic Dataset Generation - Complete Summary

Three powerful approaches to generate realistic Q&A datasets for RAG testing.

## The Three Generators at a Glance

```
┌─────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
│   TEMPLATE-BASED    │     LLM-FROM-FAQ     │   PRODUCT-CENTRIC    │   RAGAS-BASED        │
├─────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Speed:       ⚡⚡⚡  │ Speed:        ⚡⚡   │ Speed:         ⚡   │ Speed:           ⚡  │
│ Cost:        💰     │ Cost:       💰💰    │ Cost:        💰💰   │ Cost:        💰💰💰   │
│ Quality:     ⭐⭐   │ Quality:     ⭐⭐⭐  │ Quality:       ⭐⭐⭐ │ Quality:      ⭐⭐⭐⭐  │
│ Realistic:   ⭐⭐   │ Realistic:   ⭐⭐⭐  │ Realistic:     ⭐⭐⭐ │ Realistic:    ⭐⭐⭐⭐  │
│ Grounded:    ❌      │ Grounded:    ✅      │ Grounded:      ✅    │ Grounded:      ✅    │
└─────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

## Quick Reference Table

| Feature | Template | LLM-FAQ | Product | RAGAS |
|---------|----------|---------|---------|-------|
| **Input** | Pre-defined templates | Existing FAQ | Product description | Documents |
| **Speed** | <1 min for 1000 | 10-30 min/1000 | 15-30 min/500 | 1-2 hrs/500 |
| **Cost** | $0 | $0.50-1.00/1000 | $0.25-0.50/500 | $2-5/500 |
| **Requires FAQ** | ❌ No | ✅ Yes | ❌ No | ✅ Yes |
| **Diversity** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Groundedness** | No | Yes (from FAQ) | Yes (from description) | Yes (from docs) |
| **Reproducible** | ✅ Yes (with seed) | Partially | No | No |
| **Evaluation data** | ❌ | ⚠️ Basic | ⚠️ Basic | ✅ Full |
| **Use case** | Dev/testing | Expand FAQ | Generate from scratch | Production eval |

---

## Which Generator Should I Use?

### 📋 Decision Tree

**Do you have existing FAQ?**
- **YES** → Use LLM-FROM-FAQ
  - Fast, cheap, quality is high
  - Generates variations of your real FAQ
  - Best for expanding documentation

- **NO** → Two options:

  1. **Need quick testing?**
     - Use TEMPLATE-BASED
     - Instant, free, reproducible
     - Good for development and CI/CD

  2. **Need production quality?**
     - Use PRODUCT-CENTRIC
     - More realistic, grounded in description
     - Takes 15-30 min but worth it

**Need professional-grade evaluation?**
- Use RAGAS-BASED
- Comprehensive, industry-standard
- Best for final RAG assessment

---

## Three Generators Explained

### Generator 1: Template-Based
**File:** `scripts/generate_synthetic_qa.py`

**Use this if:** You need quick, deterministic data for testing

```bash
python scripts/generate_synthetic_qa.py \
    --count 1000 \
    --output datasets/qa_template_1000.json \
    --seed 42 \
    --include-eval
```

**How it works:**
- 5 predefined categories (Account, Billing, Technical, Features, Getting Started)
- Random selection + paraphrasing templates
- Deterministic with seed

**Pros:**
- ⚡ Fastest (1000 pairs in <1 second)
- 💰 Free (no API costs)
- ✅ Reproducible (same seed = same data)
- Works offline

**Cons:**
- Limited diversity
- Generic, not product-specific
- Not grounded in real FAQ

**Best for:**
- Development and debugging
- CI/CD pipelines
- Performance benchmarking
- Quick prototyping

---

### Generator 2: LLM-From-FAQ
**File:** `scripts/generate_qa_from_faq.py`

**Use this if:** You have existing FAQ and want to expand it with variations

```bash
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_expanded_500.json \
    --variations 5
```

**How it works:**
- Reads your actual FAQ as ground truth
- LLM generates 5 paraphrases per question
- Auto-classifies intent, category, difficulty
- Generates related questions

**Example transformations:**
```
Original: "How do I reset my password?"
↓
Variations:
1. "I forgot my password. How can I recover it?"
2. "What's the process to change my password?"
3. "How do I regain access to my account?"
4. "Can you help me reset my login credentials?"
5. "What should I do if I lost my password?"
```

**Pros:**
- ✅ Grounded in your real FAQ
- ✅ Diverse paraphrasing (5+ variations)
- ✅ Auto-classification
- ✅ Reasonable cost

**Cons:**
- Requires OpenAI API key
- 10-30 min per 1000 pairs
- Depends on LLM quality

**Best for:**
- Expanding existing FAQ
- Quality evaluation of real docs
- Production dataset generation

---

### Generator 3: Product-Centric
**File:** `scripts/generate_qa_from_product.py`

**Use this if:** You need to generate FAQ from scratch for any product/service

```bash
python scripts/generate_qa_from_product.py \
    --product-name "CloudDrive" \
    --description "Enterprise cloud storage with real-time collaboration" \
    --industry "SaaS" \
    --count 500 \
    --output datasets/qa_clouddrive_500.json
```

**How it works:**
- Takes product description as input
- Selects industry-specific categories (6 categories)
- LLM generates realistic Q&A for each category
- Includes metadata (intent, difficulty, tags)

**Supported industries:**
- SaaS (productivity, analytics, collaboration tools)
- E-commerce (online stores, marketplaces)
- Fintech (payments, banking, investing)
- Social Media (content sharing, communities)
- Marketplace (peer-to-peer platforms)
- Generic (anything else)

**Pros:**
- ✅ Works without existing FAQ
- ✅ Industry-specific categories
- ✅ Highly realistic
- ✅ Scalable to any size

**Cons:**
- Requires OpenAI API
- 15-30 min per 500 pairs
- More expensive than LLM-FAQ

**Best for:**
- Generating FAQ from scratch
- New products without documentation
- Testing RAG on various product types

---

### Generator 4: RAGAS-Based
**File:** `scripts/generate_qa_ragas.py`

**Use this if:** You need professional-grade evaluation data

```bash
pip install ragas

python scripts/generate_qa_ragas.py \
    --documents datasets/qa_data.json \
    --output datasets/qa_ragas_500.json \
    --num-pairs 500 \
    --evolutions simple reasoning multi_context
```

**How it works:**
- Industry-standard RAGAS framework
- Generates question evolutions:
  - **Simple**: Direct paraphrases
  - **Reasoning**: Multi-step thinking
  - **Multi-context**: Multiple chunks needed
- Built-in ground truth for evaluation

**Pros:**
- ⭐ Industry-standard approach
- ⭐ Maximum diversity
- ⭐ Built-in evaluation metrics
- ⭐ Best accuracy

**Cons:**
- Requires RAGAS library
- Most expensive ($2-5 per 500)
- Slowest (30 min - 2 hrs)
- Complex setup

**Best for:**
- Production RAG evaluation
- Academic research
- High-stakes applications

---

## Workflow Recommendations

### Scenario 1: Development & Testing
```bash
# 1. Quick setup (instant)
python scripts/generate_synthetic_qa.py --count 100 --seed 42

# 2. Test your RAG pipeline
python scripts/ingest.py --file datasets/qa_synthetic_test_100.json

# 3. Measure initial performance
python evaluate_retrieval.py --qa-file datasets/qa_synthetic_test_100.json
```

**Time:** <2 minutes | **Cost:** $0

---

### Scenario 2: Expanding Existing FAQ
```bash
# 1. Generate variations from your FAQ
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_expanded_500.json \
    --variations 3

# 2. Ingest expanded dataset
python scripts/ingest.py --file datasets/qa_expanded_500.json

# 3. Evaluate quality improvement
python evaluate_retrieval.py --qa-file datasets/qa_expanded_500.json
```

**Time:** 10-15 minutes | **Cost:** ~$0.25

---

### Scenario 3: New Product Launch
```bash
# 1. Generate product-specific FAQ
python scripts/generate_qa_from_product.py \
    --product-name "MyNewApp" \
    --description "Description of my product" \
    --industry "SaaS" \
    --count 300 \
    --output datasets/qa_mynewapp_300.json

# 2. Test with RAG
python scripts/ingest.py --file datasets/qa_mynewapp_300.json
python evaluate_retrieval.py --qa-file datasets/qa_mynewapp_300.json

# 3. If quality good, generate more
python scripts/generate_qa_from_product.py \
    --product-name "MyNewApp" \
    --description "Description" \
    --industry "SaaS" \
    --count 700 \
    --output datasets/qa_mynewapp_700.json
```

**Time:** 20-30 minutes | **Cost:** ~$0.50

---

### Scenario 4: Production Evaluation
```bash
# 1. Generate comprehensive test set
python scripts/generate_qa_ragas.py \
    --documents datasets/qa_data.json \
    --output datasets/qa_ragas_eval.json \
    --num-pairs 500 \
    --evolutions simple reasoning multi_context

# 2. Run complete evaluation
python evaluate_retrieval.py \
    --qa-file datasets/qa_ragas_eval.json \
    --eval-file datasets/qa_ragas_eval.json

# 3. Generate metrics report
python evaluate_retrieval.py \
    --qa-file datasets/qa_ragas_eval.json \
    --metrics recall precision faithfulness
```

**Time:** 1-2 hours | **Cost:** $2-5

---

## Cost Comparison

For **500 Q&A pairs**:

| Generator | API Calls | Cost | Time |
|-----------|-----------|------|------|
| Template | 0 | $0.00 | <1 min |
| LLM-FAQ | ~500 | $0.25 | 8-12 min |
| Product | ~500 | $0.50 | 15-20 min |
| RAGAS | ~5000 | $3.00 | 60+ min |

---

## Running All Generators

Create a complete dataset suite:

```bash
#!/bin/bash

echo "🚀 Generating complete Q&A dataset suite..."

# 1. Template-based (free, fast)
python scripts/generate_synthetic_qa.py \
    --count 200 \
    --output datasets/qa_template_200.json \
    --seed 42

# 2. From existing FAQ (if you have one)
if [ -f "datasets/qa_data.json" ]; then
    python scripts/generate_qa_from_faq.py \
        --faq-file datasets/qa_data.json \
        --output datasets/qa_faq_expanded_300.json \
        --variations 3
fi

# 3. Product-based (requires OPENAI_API_KEY)
if [ ! -z "$OPENAI_API_KEY" ]; then
    python scripts/generate_qa_from_product.py \
        --product-name "MyProduct" \
        --description "My product description" \
        --industry "SaaS" \
        --count 300 \
        --output datasets/qa_product_300.json
fi

echo "✨ Generation complete!"
ls -lh datasets/qa_*.json
```

---

## Output Format (All Generators)

All generators produce the same compatible format:

```json
{
  "question": "How do I reset my password?",
  "answer": "Click 'Forgot Password' on login page...",
  "metadata": {
    "category": "Account",
    "intent": "reset_password",
    "difficulty": "easy|medium|hard",
    "confidence_score": 0.85,
    "requires_handoff": false,
    "tags": ["common", "faq_derived"],
    "source_document": "generated.json",
    "generated_at": "2026-01-07T12:27:06"
  }
}
```

This means you can:
- ✅ Mix datasets from different generators
- ✅ Use them interchangeably for ingestion
- ✅ Compare quality between approaches

---

## Quick Start by Use Case

### "I want to test my RAG right now"
```bash
python scripts/generate_synthetic_qa.py --count 100 --seed 42
```
⏱️ 1 second | 💰 Free

### "I have FAQ and want more variations"
```bash
python scripts/generate_qa_from_faq.py --faq-file datasets/qa_data.json --output datasets/qa_expanded.json --variations 5
```
⏱️ 10-15 minutes | 💰 ~$0.25

### "I need FAQ for my new product"
```bash
python scripts/generate_qa_from_product.py --product-name "MyApp" --description "..." --industry "SaaS" --count 500 --output datasets/qa_myapp.json
```
⏱️ 15-30 minutes | 💰 ~$0.50

### "I need production-grade evaluation"
```bash
python scripts/generate_qa_ragas.py --documents datasets/qa_data.json --output datasets/qa_ragas.json --num-pairs 500
```
⏱️ 1-2 hours | 💰 $2-5

---

## Documentation

- **SYNTHETIC_DATA_GUIDE.md** - Original template generator details
- **SYNTHETIC_DATA_ADVANCED_GUIDE.md** - Template vs LLM vs RAGAS comparison
- **PRODUCT_BASED_FAQ_GUIDE.md** - Product-centric generator guide (with examples for each industry)

---

## Next Steps

1. **Understand your need** - pick a scenario above
2. **Run appropriate generator** - use quick start commands
3. **Test with your RAG** - ingest and evaluate
4. **Iterate** - adjust parameters based on results
5. **Scale up** - generate larger datasets when satisfied

🎯 **Most users should start with either:**
- **Template-based** for quick development testing
- **Product-centric** for realistic production datasets
