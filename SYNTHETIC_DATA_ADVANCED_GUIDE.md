# Advanced Synthetic Q&A Generation Guide

Professional approaches to generating diverse, high-quality synthetic datasets for RAG testing.

## Three Approaches Compared

### 1. **Template-Based Generation** (Quick & Deterministic)
**File**: `scripts/generate_synthetic_qa.py`

```bash
python scripts/generate_synthetic_qa.py --count 1000 --output datasets/qa_synthetic.json
```

**How it works:**
- Uses pre-defined questions, answers, and intents in memory
- Randomly combines them with variations
- Fast and reproducible (with seed)

**Pros:**
- ⚡ Fastest (instant for 1000 pairs)
- 🎯 Fully reproducible (same seed = same data)
- 💰 No API costs
- ✅ Works offline

**Cons:**
- ❌ Limited diversity (bounded by templates)
- ❌ Less realistic paraphrasing
- ❌ Not grounded in actual FAQ

**Use cases:**
- Quick testing and debugging
- CI/CD pipelines
- Performance benchmarking
- Reproducible testing

---

### 2. **LLM-Based Generation from FAQ** (Balanced)
**File**: `scripts/generate_qa_from_faq.py`

```bash
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_llm_generated.json \
    --variations 5
```

**How it works:**
- Reads your **actual FAQ** as ground truth
- LLM paraphrases each question in 5 different ways
- LLM classifies intent, category, difficulty automatically
- Generates related questions for each answer
- Each original pair becomes 5 unique variations

**Example:**
```
Original: "How do I reset my password?"
Generated:
1. "I forgot my password. How can I change it?"
2. "What's the process to recover my account password?"
3. "How do I reset my account if I've lost my password?"
4. "Can you help me reset my login credentials?"
5. "What should I do if I can't remember my password?"
```

**Pros:**
- ✅ **Grounded in actual FAQ** (realistic)
- ✅ **Diverse paraphrasing** (5+ variations per original)
- ✅ **Auto-classification** (intent, category, difficulty)
- ✅ **Reasonable cost** (~$0.01-0.10 per 100 original pairs)
- ✅ **Related questions** (understands context)

**Cons:**
- ⚠️ Requires OpenAI API key
- ⚠️ Slower (~10-30 min for 1000 pairs)
- ⚠️ Quality depends on LLM

**Use cases:**
- Production dataset generation
- Expanding your FAQ with variations
- Quality evaluation
- Real-world testing

---

### 3. **RAGAS TestsetGenerator** (Professional-Grade)
**File**: `scripts/generate_qa_ragas.py`

```bash
pip install ragas

python scripts/generate_qa_ragas.py \
    --documents datasets/qa_data.json \
    --output datasets/qa_ragas.json \
    --num-pairs 500 \
    --evolutions simple reasoning multi_context
```

**How it works:**
- Industry-standard approach used by OpenAI, Anthropic RAG teams
- Treats FAQ answers as "documents/context"
- LLM generates **diverse question evolutions**:
  - **Simple**: Direct paraphrases
  - **Reasoning**: Questions requiring multi-step thinking
  - **Multi-context**: Questions needing multiple chunks
- Automatically creates evaluation ground truth

**Example evolutions:**
```
Context: "You can reset your password by clicking 'Forgot Password' on login page"

Simple: "How do I reset my password?"
Reasoning: "What's the best practice for maintaining password security?"
Multi-context: "How do password reset and 2FA work together for account security?"
```

**Pros:**
- ✅ **Professional-grade** (industry standard)
- ✅ **Maximum diversity** (3+ evolution types)
- ✅ **Built-in evaluation** (ground truth included)
- ✅ **Best accuracy** (sophisticated generation)
- ✅ **Realistic** (mimics real user questions)

**Cons:**
- ⚠️ Requires RAGAS library (pip install ragas)
- ⚠️ **Most expensive** (~$0.50-2.00 per 100 pairs)
- ⚠️ **Slowest** (30min-2hrs for 1000 pairs)
- ⚠️ Complex setup

**Use cases:**
- Production RAG evaluation
- Academic research
- High-stakes applications
- Comprehensive testing

---

## Decision Matrix: Which One to Use?

| Need | Quick Test | Expand FAQ | Production Quality |
|------|-----------|-----------|------------------|
| Speed | ✅ Template | ⚠️ LLM | ❌ RAGAS |
| Cost | ✅ Free | ✅ $0.01-0.10 | ❌ $0.50-2.00 |
| Diversity | ⚠️ Limited | ✅ Good | ✅✅ Excellent |
| Realistic | ⚠️ Generic | ✅ Good | ✅✅ Excellent |
| Grounded in FAQ | ❌ No | ✅ Yes | ✅ Yes |
| Evaluation data | ❌ No | ⚠️ Basic | ✅ Complete |

---

## Workflow Recommendation

### Phase 1: Development
```bash
# Use template-based for quick iteration
python scripts/generate_synthetic_qa.py --count 100 --seed 42
```

### Phase 2: Testing
```bash
# Use LLM-based from your real FAQ
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_testing.json \
    --variations 3
```

### Phase 3: Production Evaluation
```bash
# Use RAGAS for comprehensive evaluation
python scripts/generate_qa_ragas.py \
    --documents datasets/qa_data.json \
    --output datasets/qa_production.json \
    --num-pairs 500 \
    --evolutions simple reasoning
```

---

## Data Format Consistency

All three methods output compatible formats:

```json
{
  "question": "How do I reset my password?",
  "answer": "You can reset your password by clicking...",
  "metadata": {
    "category": "Account",
    "intent": "reset_password",
    "difficulty": "easy|medium|hard",
    "confidence_score": 0.85,
    "requires_handoff": false,
    "tags": ["common_question", "faq_derived"],
    "source_document": "qa_data.json",
    "generated_at": "2026-01-07T12:27:06.802358"
  }
}
```

This means you can:
- Mix datasets from different generators
- Compare quality between approaches
- Use them interchangeably for ingestion

---

## Quick Start Commands

### 1. Template-Based (1 minute)
```bash
# Generate 1000 pairs instantly
python scripts/generate_synthetic_qa.py \
    --count 1000 \
    --output datasets/qa_template_1000.json \
    --include-eval
```

### 2. LLM-Based (10-30 minutes)
```bash
# Generate from your FAQ
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_llm_500.json \
    --variations 5
```

### 3. RAGAS-Based (30 minutes - 2 hours)
```bash
# First install
pip install ragas langchain-community

# Then generate
python scripts/generate_qa_ragas.py \
    --documents datasets/qa_data.json \
    --output datasets/qa_ragas_500.json \
    --num-pairs 500 \
    --evolutions simple reasoning multi_context
```

---

## Comparison: Example Output

**Original FAQ pair:**
```
Q: "How do I reset my password?"
A: "Click 'Forgot Password' on the login page and follow the email instructions."
```

### Template-Based Output (3 variations):
```
1. "What's the way to reset my password?"
2. "Can you help me reset my password?"
3. "How do I reset my password please?"
```
*Note: Quick variations, may not be semantically different*

### LLM-Based Output (5 variations):
```
1. "I forgot my password, how can I recover it?"
2. "What's the process to change my password?"
3. "My account password needs resetting - what should I do?"
4. "How do I regain access if I can't remember my password?"
5. "What steps do I take to reset my login credentials?"
```
*Note: Diverse, natural, grounded in FAQ context*

### RAGAS Output (evolutions):
```
Simple:
"I need to reset my password. What's the process?"

Reasoning:
"What security measures are in place for password reset?"

Multi-context:
"How does password reset work alongside two-factor authentication?"
```
*Note: Realistic, diverse question types, evaluation-ready*

---

## Cost Comparison (For 1000 pairs)

| Method | API Calls | Cost | Time |
|--------|-----------|------|------|
| Template | 0 | $0 | <1 min |
| LLM-Based | ~1000 | $0.50-1.00 | 15-30 min |
| RAGAS | ~5000 | $2.00-5.00 | 1-2 hours |

---

## Production Recommendation

For **production FAQ** testing:

1. **Start with LLM-based** (good balance)
   - Cost: Reasonable ($0.01 per original pair)
   - Quality: Good diversity
   - Speed: Acceptable
   - Use: Expand FAQ with variations, test quality

2. **Validate with RAGAS** (final evaluation)
   - Use for final benchmarking
   - Generate evaluation ground truth
   - Measure Ragas metrics (recall, precision, faithfulness)
   - Cost: Worth it for production assurance

3. **Use Template-based for CI/CD**
   - Reproducible testing
   - No API costs
   - Deterministic results

---

## Troubleshooting

### "OpenAI API key not found"
```bash
# Set your API key
export OPENAI_API_KEY="sk-..."
```

### "RAGAS not installed"
```bash
pip install ragas langchain-community langchain-text-splitters
```

### "LLM generation too slow"
```bash
# Use fewer variations
python scripts/generate_qa_from_faq.py \
    --faq-file datasets/qa_data.json \
    --output datasets/qa_llm.json \
    --variations 2  # Instead of default 3
```

### "Quality of generated questions is poor"
- Use RAGAS instead (better quality)
- Or manually curate FAQ first before generation
- Check your LLM temperature (lower = more consistent)

---

## Next Steps

1. **Pick an approach** based on your needs
2. **Generate a test dataset** with 100 pairs
3. **Ingest into your RAG** pipeline
4. **Measure metrics** (recall, precision, faithfulness)
5. **Compare approaches** to find best balance for your use case

See `SYNTHETIC_DATA_GUIDE.md` for original simple generator documentation.
