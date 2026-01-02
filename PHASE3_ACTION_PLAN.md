# PHASE 3 - ПЛАН ДЕЙСТВИЙ (БЕЗ КОДА)

## 🎯 ВЫБРАННЫЙ ПОДХОД: Zero-shot BERT

**Причины:**
- ✅ No training needed (works out of box)
- ✅ Good quality for intent/category classification
- ✅ Open source, free
- ✅ Easy to extend (just add new intent/category)
- ✅ Fast (~100-200ms per question)
- ✅ Perfect for MVP

**Model:** `facebook/bart-large-mnli` from HuggingFace

---

## 📋 СТРУКТУРА ФАЗЫ 3

### TASK 3.1: Classification Node (Zero-shot BERT)

**Files to create:**
```
app/nodes/classification/
  ├── __init__.py
  ├── prompts.py          ← Define INTENTS and CATEGORIES lists
  ├── models.py           ← ClassificationOutput Pydantic model
  ├── classifier.py       ← ClassificationService class (singleton)
  └── node.py             ← LangGraph node wrapper
```

**What to do:**
1. Define all possible intents (faq, complaint, suggestion, etc.)
2. Define all possible categories (billing, shipping, account, etc.)
3. Create zero-shot classifier using transformers pipeline
4. Implement async classification for both intent + category
5. Add simple caching (LRU) for same questions
6. Wrap as LangGraph node
7. Integrate into graph as FIRST node (before retrieve)

**Integration:**
- Update `app/pipeline/state.py` → add: intent, intent_confidence, category, category_confidence, all_category_scores
- Update `app/pipeline/graph.py` → add classify_node as START node
- Update `requirements.txt` → add transformers, torch

**Testing:**
- Create `scripts/test_classification.py` for basic testing

---

### TASK 3.2: Metadata Filtering Node (with safety)

**Files to create:**
```
app/nodes/metadata_filtering/
  ├── __init__.py
  ├── models.py           ← FilteringOutput Pydantic model
  ├── filtering.py        ← MetadataFilteringService class (singleton)
  └── node.py             ← LangGraph node wrapper
```

**What to do:**
1. Create filtering service with safety mechanisms:
   - If category_confidence < threshold → skip filter (search all docs)
   - If filter returns < min_results → FALLBACK to full search
   - Log why fallback happened

2. Implement filtering logic:
   - Update `app/storage/vector_store.py` → add optional `category_filter` parameter
   - Add WHERE clause for metadata filtering in SQL

3. Wrap as LangGraph node that:
   - Takes: question, category (from classify), category_confidence
   - Returns: docs, filter_used flag, fallback_triggered flag

4. Integrate into graph between classify and retrieve

**Integration:**
- Update `app/pipeline/state.py` → add: filter_used, fallback_triggered, filtering_reason
- Update `app/pipeline/graph.py` → add metadata_filter_node between classify and retrieve
- Update `app/storage/vector_store.py` → support category_filter parameter

**Testing:**
- Create `scripts/test_filtering.py` for testing filter + fallback behavior

---

### TASK 3.3: Improve Routing Logic

**Files to update:**
```
app/nodes/routing/
  ├── logic.py            ← Update decide_action function
  └── node.py             ← Update route_node to compute scores
```

**What to do:**
1. Update routing logic to use multiple confidence metrics:
   - Instead of: `if confidence >= threshold → auto_reply else → handoff`
   - New approach:
     ```
     if generation_confidence > 0.85 and faithfulness > 0.8:
         return "auto_reply"
     elif generation_confidence > 0.5:
         return "needs_review"
     elif fallback_triggered:
         return "needs_review"  (be cautious if filter fallback)
     else:
         return "escalation"
     ```

2. Compute generation_confidence in route_node:
   - `generation_confidence = (faithfulness_score + relevancy_score) / 2`

3. Store all scores in state for logging/debugging

**Integration:**
- Update `app/pipeline/state.py` → add: generation_confidence, faithfulness_score, relevancy_score
- Update `app/nodes/routing/logic.py` → new decide_action signature
- Update `app/nodes/routing/node.py` → compute generation_confidence
- Update `app/api/routes.py` → return all scores in `/ask` response

**Testing:**
- Manual testing with different confidence scenarios

---

## 📊 UPDATED GRAPH FLOW

```
START
  ↓
[classify_node]
  → intent, category, intent_confidence, category_confidence
  ↓
[metadata_filter_node]
  → filter docs by category (with fallback safety)
  → docs, filter_used, fallback_triggered
  ↓
[retrieve_node]
  → vector search
  → docs, confidence
  ↓
[route_node]
  → compute generation_confidence
  → decide: auto_reply vs needs_review vs escalation
  ↓
CONDITION:
├─ auto_reply → generate → END
├─ needs_review → END (marked for review)
└─ escalation → END (marked for escalation)
```

---

## ✅ DEFINITION OF DONE

- ✅ Classification node works (zero-shot BERT)
- ✅ Metadata filtering with safety (fallback logic)
- ✅ Routing logic uses all confidence metrics
- ✅ State has all needed fields
- ✅ Graph integrated all nodes in right order
- ✅ Storage layer supports category filtering
- ✅ API returns all scores and stats
- ✅ All loggers configured
- ✅ Tests pass
- ✅ Ready to commit

---

## 🚀 EXECUTION ORDER

1. **Task 3.1** (1-2 days)
   - Create classification node
   - Test with sample questions
   - Verify model loads correctly

2. **Task 3.2** (1-2 days)
   - Create metadata filtering node
   - Update storage for category filtering
   - Test filter + fallback behavior
   - Verify SQL queries work

3. **Task 3.3** (0.5 day)
   - Update routing logic
   - Update API response
   - Test different confidence scenarios

4. **Integration & Testing** (0.5 day)
   - Full pipeline end-to-end test
   - Manual testing with real questions
   - Check all logging works

---

## 📝 NOTES

**Dependencies to add to requirements.txt:**
- transformers>=4.30.0
- torch>=2.0.0  (or torch-cpu for lightweight)
- scikit-learn>=1.3.0 (optional, for future enhancements)

**Model will be downloaded on first use:**
- facebook/bart-large-mnli (~1.6GB)
- Downloaded to ~/.cache/huggingface/

**Safety thresholds (configurable in settings):**
- INTENT_CONFIDENCE_THRESHOLD: 0.5 (minimum to trust intent)
- CATEGORY_CONFIDENCE_THRESHOLD: 0.4 (minimum to use filter)
- MIN_RESULTS_FOR_FILTER: 2 (minimum docs before fallback)
- GENERATION_CONFIDENCE_AUTO_REPLY: 0.85
- GENERATION_CONFIDENCE_NEEDS_REVIEW: 0.5

**Caching strategy:**
- Classification results cached by question hash (LRU)
- No external cache needed initially
- Can upgrade to Redis later

---

## ⚠️ POTENTIAL ISSUES & MITIGATIONS

| Issue | Mitigation |
|-------|-----------|
| Model slow on CPU | Use GPU if available, quantize model |
| Category filter too strict | Lower thresholds, adjust min_results |
| Fallback triggered too often | Add more docs to categories |
| Wrong classifications | Zero-shot can be wrong sometimes, log for analysis |

---

## 📊 WHAT GETS BETTER AFTER PHASE 3

**Before Phase 3:**
- Search: vector only, no filtering → low precision
- Routing: simple confidence threshold → many false escalations
- Debugging: hard to understand why escalation happened

**After Phase 3:**
- Search: vector + category filter → higher precision
- Routing: multi-metric decision → fewer false escalations
- Debugging: detailed logs for each step (classify, filter, generation)
- API: returns all confidence scores for transparency
