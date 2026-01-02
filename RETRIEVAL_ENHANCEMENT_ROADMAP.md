# Support RAG - Retrieval Enhancement Roadmap

**Comprehensive implementation plan for Phases 3-4 of the Support RAG pipeline.**

---

## 📊 Current Status

### ✅ Phases 1-2: COMPLETE
- Retrieval metrics: Hit Rate, MRR, Exact Match
- Generation metrics: Faithfulness, Relevancy
- Benchmarking framework with multiple scripts
- Full Langfuse integration
- LangGraph pipeline: retrieve → route → generate

---

## 🎯 PHASE 3: Intent-Based Retrieval Optimization (~4 days)

### 3.1 Classification Node (Zero-shot BERT)
**Without training. No dependencies.**

**What:** Classify user questions into intents and categories at the start of pipeline.

**Intents:** faq, complaint, suggestion, technical, billing, account
**Categories:** billing, shipping, account, product, returns, technical, general

**How:**
- Use `facebook/bart-large-mnli` zero-shot classification (HuggingFace transformers)
- Async classification for both intent + category in parallel
- Simple LRU cache for repeated questions
- Singleton service pattern

**Files to create:**
```
app/nodes/classification/
  ├── prompts.py        (define intents/categories)
  ├── classifier.py     (ClassificationService with zero-shot logic)
  ├── models.py         (ClassificationOutput Pydantic model)
  └── node.py          (LangGraph node wrapper)
```

**Integration:**
- Update `app/pipeline/state.py` → add: intent, intent_confidence, category, category_confidence
- Update `app/pipeline/graph.py` → add classify_node as START node
- Update `requirements.txt` → add: transformers>=4.30.0, torch>=2.0.0

**Benefits:**
- ✅ Fast (~100-200ms, no API calls)
- ✅ Free
- ✅ Deterministic (same input = same output)
- ✅ Enables category-aware retrieval

---

### 3.2 Metadata Filtering Node (with Safety Fallback)
**Smart filtering with safety mechanisms.**

**What:** Filter documents by classified category to improve precision.

**Safety Logic:**
```
if category_confidence < 0.5:
    skip filtering → search all documents
elif retrieve(category) returns >= 2 docs:
    use filtered results
else:
    FALLBACK to full search (log warning)
```

**How:**
- Update `app/storage/vector_store.py` → add optional `category_filter` parameter
- Add SQL WHERE clause: `metadata->>'category' = %s`
- Create filtering service with fallback logic
- Log all filtering decisions for monitoring

**Files to create:**
```
app/nodes/metadata_filtering/
  ├── filtering.py      (MetadataFilteringService with fallback)
  ├── models.py         (FilteringOutput with stats)
  └── node.py          (LangGraph node wrapper)
```

**Integration:**
- Update `app/pipeline/state.py` → add: filter_used, fallback_triggered, filtering_reason
- Update `app/pipeline/graph.py` → add metadata_filter_node between classify and retrieve
- Update `app/storage/vector_store.py` → category_filter parameter support

**Benefits:**
- ✅ Higher precision (filter by category)
- ✅ Safety first (fallback if needed)
- ✅ Observable (log all decisions)

---

### 3.3 Improve Routing Logic
**Multi-metric decision making.**

**Current:** `if confidence >= threshold → auto_reply else → handoff` (binary)

**New:** 3-way routing based on multiple confidence scores
```
if generation_confidence > 0.85 and faithfulness > 0.8:
    → auto_reply
elif generation_confidence > 0.5:
    → needs_review
else:
    → escalation
```

**How:**
- Compute `generation_confidence = avg(faithfulness_score, relevancy_score)` in route_node
- Factor in `fallback_triggered` (be cautious if filter had to fallback)
- Store all scores in state for logging/debugging

**Files to update:**
```
app/nodes/routing/
  ├── logic.py         (update decide_action signature)
  └── node.py         (compute generation_confidence)
```

**Integration:**
- Update `app/pipeline/state.py` → add: generation_confidence, faithfulness_score, relevancy_score
- Update `app/api/routes.py` → return all scores in `/ask` response JSON
- Update routing to handle 3+ outcomes

**Benefits:**
- ✅ Better routing (uses multiple metrics)
- ✅ Transparent (can see all scores)
- ✅ Safer (accounts for fallback flag)

---

## 🎯 PHASE 4: Advanced Retrieval Nodes (~5-7 days optional)

### Strategy: Rule-Based + LLM Hybrid

Choose one of these options:

---

### Option A: Production-Ready with Rule-Based (~5-6 days) ⭐ RECOMMENDED

**Fast, cheap, optimized for domain.**

#### 4.1 Slang Normalizer (0.5 day)
- Transform product-specific slang into standard terms
- Example: "pipe" → "pipeline", "rejectable" → "rejected records"
- Implementation: Simple dictionary + word-level replacement
- File: `app/nodes/slang_normalizer/normalizer.py`

#### 4.2 Spelling Correction (0.5 day)
- Fix typos before search (use pyspellchecker or autocorrect library)
- Example: "configer" → "configure"
- Implementation: Pre-trained library + domain terms
- File: `app/nodes/spelling_correction/corrector.py`

#### 4.3 Synonym Expansion (1 day)
- Expand question with domain-specific synonyms
- Example: "return" → ["refund", "send back", "money back"]
- Implementation: YAML dictionary + keyword matching
- File: `app/nodes/synonym_expansion/expander.py`

#### 4.4 Rule-Based Reformulation (2 days)
- Regex pattern-based query reformulation (no LLM!)
- Example: "error: 404" → add "troubleshooting", "debug", "fix"
- Implementation: Regex patterns + action engine
- File: `app/nodes/rule_reformulation/engine.py`

#### 4.5 Intent-Aware Synonyms (1 day)
- Use different synonyms per intent/category
- Example: "order" (billing) vs "order" (shipping) → different synonyms
- Implementation: Intent-keyed dictionary
- File: `app/nodes/intent_synonyms/mapper.py`

**Integration order:**
```
classify → slang_normalizer → spelling_correction →
intent_aware_synonyms → synonym_expansion →
rule_reformulation → metadata_filter → retrieve
```

**Result:** Fast, deterministic, fully customizable for your domain.

---

### Option B: Full-Featured (~7-9 days)

**Everything from Option A + advanced LLM + reasoning.**

Add to Option A:

#### 4.6 LLM Query Reformulation (1-2 days)
- Generate 2-3 reformulations using gpt-4o-mini
- Learns patterns from your domain
- Implementation: LangChain LLM + prompt template
- File: `app/nodes/llm_reformulation/reformulator.py`

#### 4.7 Multi-Hop Reasoning (2-3 days)
- For complex questions, find chains of related documents
- Detect complexity → retrieve top-1 → find related → combine
- Implementation: Complexity scorer + hop resolver
- Files: `app/nodes/multihop/complexity_detector.py`, `hop_resolver.py`

#### 4.8 Cross-Reference Resolution (1 day)
- Find documents linked via metadata.see_also
- Example: FAQ links to "Return Policy" → retrieve both
- Implementation: Link parser + batch retrieval
- File: `app/nodes/cross_reference/resolver.py`

#### 4.9 Semantic Clustering (1 day)
- Group similar documents together
- Reduces redundancy, better context organization
- Implementation: Embedding similarity + clustering
- File: `app/nodes/clustering/clusterer.py`

**Result:** Handles complex questions, but slower and more expensive.

---

## 📊 Comparison

| | Option A (Rule-Based) | Option B (Full) |
|---|---|---|
| **Speed** | ⚡ Fast (no API calls) | Slower (LLM calls) |
| **Cost** | Free | 💰 Per request |
| **Setup Time** | 5-6 days | 7-9 days |
| **Customization** | Easy (just rules) | Medium (rules + prompts) |
| **Best For** | Domain-specific support | General + complex Q&A |
| **Maintenance** | Simple | More complex |

---

## 🔄 Final Pipeline Architecture

### After Phase 3 (Required):
```
START → classify → metadata_filter → retrieve →
route → [generate or END]
```

### After Phase 4 (Optional):
```
START → slang_normalizer → spelling_correction →
classify → intent_synonyms → synonym_expansion →
rule_reformulation → metadata_filter → retrieve →
[rerank → clustering → cross_reference → multihop] →
merge_context → generate → route → END
```

---

## 📝 Implementation Summary

### Phase 3 Files to Create:
```
app/nodes/classification/
  ├── __init__.py
  ├── prompts.py
  ├── classifier.py
  ├── models.py
  └── node.py

app/nodes/metadata_filtering/
  ├── __init__.py
  ├── filtering.py
  ├── models.py
  └── node.py
```

### Phase 3 Files to Update:
```
app/pipeline/state.py        (add new fields)
app/pipeline/graph.py        (integrate new nodes)
app/nodes/routing/logic.py   (multi-metric routing)
app/nodes/routing/node.py    (compute scores)
app/storage/vector_store.py  (category filter)
app/api/routes.py            (enhanced responses)
requirements.txt             (transformers, torch)
```

### Phase 4 Files to Create (if chosen):
```
Option A (5 files):
- app/nodes/slang_normalizer/
- app/nodes/spelling_correction/
- app/nodes/synonym_expansion/
- app/nodes/rule_reformulation/
- app/nodes/intent_synonyms/

Option B (9 files):
- All from Option A +
- app/nodes/llm_reformulation/
- app/nodes/multihop/
- app/nodes/cross_reference/
- app/nodes/clustering/
```

---

## ⏱️ Timeline

```
Phase 3 (Required): 4 days
  - 3.1 Classification: 1-2 days
  - 3.2 Filtering: 1-2 days
  - 3.3 Routing: 0.5 day
  - Integration + testing: 0.5 day

Phase 4 (Optional):
  - Option A: 5-6 days
  - Option B: 7-9 days
  - Selective (pick 2-3 nodes): 2-3 days

Total: Phase 3 (4 days) + Phase 4 A (5-6 days) = 9-10 days for MVP
```

---

## ✅ Success Metrics

### Phase 3 Success:
- ✅ Classification accuracy: >90% on test set
- ✅ Fallback rate: <30% (filter working)
- ✅ Routing: 3-way decisions logged
- ✅ All scores returned in API

### Phase 4A Success (Rule-Based):
- ✅ No external API calls (fast)
- ✅ Deterministic results
- ✅ Easy to debug and customize
- ✅ ~30-40% improvement in recall

### Phase 4B Success (Full):
- ✅ Handles complex questions (multi-hop)
- ✅ Better query understanding
- ✅ ~50-60% improvement in recall
- ✅ Production-ready

---

## 🎯 Recommendation

**Start with:** Phase 3 (4 days) + Option A (5-6 days) = **9-10 days total**

This gives you:
- ✅ Production-ready support RAG
- ✅ Fast and cheap (no LLM calls for retrieval)
- ✅ Domain-optimized
- ✅ Easy to customize

Then optionally add LLM features (4.6, 4.7) if you see value.

---

## 📚 Testing & Documentation

Each phase should include:
- Unit tests for each node
- Integration tests for full pipeline
- Test scripts for validation
- Documentation/README for each node
- Example configurations

---

## 🚀 Next Steps

1. Choose Phase 3 (required) or skip to Phase 4
2. Choose Phase 4 option (A, B, or selective)
3. Create feature branch for implementation
4. Implement nodes in recommended order
5. Test and validate with ground truth dataset
6. Create PR with comprehensive changes
