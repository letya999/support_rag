# PHASE 3 ROADMAP - Intent-Based Retrieval Optimization

## 🎯 ВЫБРАННЫЙ ПОДХОД: Zero-shot BERT Classification

**Почему Zero-shot BERT?**
- ✅ Работает из коробки (no training needed)
- ✅ Отличное качество для intent/category классификации
- ✅ Open source и бесплатно
- ✅ Легко добавлять новые intent/category
- ✅ Быстро (~100-200ms per question)
- ✅ Идеально для MVP opensource

**Выбранная модель:** `facebook/bart-large-mnli` (через HuggingFace transformers)

---

## 📋 ПОЛНЫЙ ROADMAP ФАЗЫ 3

### ЗАДАЧА 3.1: Classification Node (Zero-shot BERT)
**Время:** 2-3 дня | **Приоритет:** 🔴 HIGH

#### 3.1.1 Создать структуру классификатора
**Файлы:**
```
app/nodes/classification/
├── __init__.py                    (empty or exports)
├── node.py                        (LangGraph node wrapper)
├── classifier.py                  (Zero-shot classifier logic)
├── models.py                      (Pydantic models for I/O)
└── prompts.py                     (Definition of intents/categories)
```

#### 3.1.2 Реализовать `app/nodes/classification/prompts.py`
**Содержит:**
```python
# Определение всех возможных интентов и категорий
INTENTS = [
    "faq",              # General question
    "complaint",        # User complaint
    "suggestion",       # User suggestion/feature request
    "billing",          # Billing related
    "technical",        # Technical issue
    "account",          # Account management
]

CATEGORIES = [
    "billing",          # Billing & payments
    "shipping",         # Shipping & delivery
    "account",          # Account & authentication
    "product",          # Product info
    "returns",          # Returns & refunds
    "technical",        # Technical support
    "general",          # General inquiry
]

# Hint phrases для улучшения классификации (optional, for zero-shot)
INTENT_HINTS = {
    "faq": ["how to", "what is", "can i", "do you", "where is"],
    "complaint": ["bad", "wrong", "broken", "not working", "issue"],
    "suggestion": ["suggest", "feature", "idea", "improvement", "better"],
    # ... etc
}
```

#### 3.1.3 Реализовать `app/nodes/classification/classifier.py`
**Содержит:**
- `ClassificationService` (singleton)
  - Загружает модель один раз: `facebook/bart-large-mnli`
  - Метод `classify_intent(question)` → (intent, confidence)
  - Метод `classify_category(question)` → (category, confidence)
  - Метод `classify_both(question)` → (intent, category, intent_conf, category_conf)
  - Кэширование результатов (LRU cache на основе question hash)

**Логика:**
```python
class ClassificationService:
    def __init__(self):
        self.pipe = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=0  # GPU if available
        )
        self.cache = {}  # Simple dict cache

    async def classify_intent(self, question: str):
        """Classify into intents"""
        result = self.pipe(
            question,
            INTENTS,
            multi_class=False  # Single label
        )
        return {
            "intent": result["labels"][0],
            "confidence": float(result["scores"][0])
        }

    async def classify_category(self, question: str):
        """Classify into categories"""
        result = self.pipe(
            question,
            CATEGORIES,
            multi_class=False
        )
        return {
            "category": result["labels"][0],
            "confidence": float(result["scores"][0])
        }

    async def classify_both(self, question: str):
        """Classify intent AND category"""
        intent_result = await self.classify_intent(question)
        category_result = await self.classify_category(question)
        return {
            "intent": intent_result["intent"],
            "intent_confidence": intent_result["confidence"],
            "category": category_result["category"],
            "category_confidence": category_result["confidence"],
            "all_category_scores": {
                cat: score
                for cat, score in zip(
                    category_result.get("labels", []),
                    category_result.get("scores", [])
                )
            }
        }
```

#### 3.1.4 Реализовать `app/nodes/classification/models.py`
**Содержит:**
```python
class ClassificationOutput(BaseModel):
    intent: str                               # faq, complaint, etc
    intent_confidence: float                  # 0.0-1.0
    category: str                             # billing, shipping, etc
    category_confidence: float                # 0.0-1.0
    all_category_scores: Dict[str, float]    # {category: score, ...}
```

#### 3.1.5 Реализовать `app/nodes/classification/node.py`
**Содержит:**
```python
@observe(as_type="span")
async def classify_node(state: Dict[str, Any]):
    """
    LangGraph node for intent & category classification
    """
    question = state.get("question", "")
    service = get_classification_service()  # Singleton

    result = await service.classify_both(question)

    return {
        "intent": result["intent"],
        "intent_confidence": result["intent_confidence"],
        "category": result["category"],
        "category_confidence": result["category_confidence"],
        "all_category_scores": result["all_category_scores"]
    }
```

#### 3.1.6 Обновить `app/pipeline/state.py`
**Добавить поля:**
```python
class State(TypedDict):
    # ... existing fields ...

    # NEW: Classification results
    intent: Optional[str]                    # faq, complaint, etc
    intent_confidence: Optional[float]       # 0.0-1.0
    category: Optional[str]                  # billing, shipping, etc
    category_confidence: Optional[float]     # 0.0-1.0
    all_category_scores: Optional[Dict[str, float]]  # All categories ranked
```

#### 3.1.7 Обновить `app/pipeline/graph.py`
**Изменить граф:**
```python
from app.nodes.classification.node import classify_node

workflow = StateGraph(State)

# Add classification as FIRST node
workflow.add_node("classify", classify_node)
workflow.add_node("expand_query", expand_query_node)
workflow.add_node("retrieve", retrieve_node)
# ... rest of nodes ...

# Update edges
workflow.add_edge(START, "classify")
workflow.add_edge("classify", "expand_query")
# ... rest of edges ...
```

#### 3.1.8 Обновить `app/config/settings.py`
**Добавить настройку:**
```python
class Settings(BaseSettings):
    # ... existing ...

    # Classification config
    INTENT_CONFIDENCE_THRESHOLD: float = 0.5  # Skip if lower
    CATEGORY_CONFIDENCE_THRESHOLD: float = 0.4  # Use fallback if lower
    USE_CLASSIFICATION: bool = True
```

#### 3.1.9 Создать `scripts/test_classification.py`
**Для тестирования:**
- Загрузить ground truth dataset
- Для каждого question:
  - Запустить classify_node
  - Сравнить с expected intent/category (if available)
  - Вычислить accuracy, precision, recall
- Вывести результаты (console + JSON report)

---

### ЗАДАЧА 3.2: Metadata Filtering Node (с safety механизмами)
**Время:** 2-3 дня | **Приоритет:** 🔴 HIGH

#### 3.2.1 Создать структуру фильтра
**Файлы:**
```
app/nodes/metadata_filtering/
├── __init__.py
├── node.py                      (LangGraph node wrapper)
├── filtering.py                 (Filtering logic with safety)
└── models.py                    (Pydantic models)
```

#### 3.2.2 Реализовать `app/nodes/metadata_filtering/filtering.py`
**Содержит:**
```python
class MetadataFilteringService:
    def __init__(self, safety_threshold=0.5, min_results=2):
        self.safety_threshold = safety_threshold
        self.min_results = min_results

    async def filter_and_search(
        self,
        question: str,
        category: Optional[str],
        category_confidence: float,
        all_category_scores: Optional[Dict[str, float]] = None,
        top_k: int = 3
    ) -> FilteringOutput:
        """
        Smart filtering with safety mechanisms

        Logic:
        1. If category_confidence < safety_threshold → skip filtering
        2. If retrieve from category AND found >= min_results → use filtered
        3. If retrieve from category AND found < min_results → FALLBACK to all
        4. Else → return all documents
        """

        # Step 1: Check if we should use filtering at all
        if category_confidence < self.safety_threshold:
            # Low confidence - skip filter
            results = await retrieve_all(question, top_k)
            return FilteringOutput(
                docs=results,
                filter_used=False,
                fallback_triggered=False,
                reason="Low category confidence - no filtering"
            )

        # Step 2: Try to retrieve from category
        if category:
            results = await retrieve_by_category(question, category, top_k)

            if len(results) >= self.min_results:
                # Success - we have enough results
                return FilteringOutput(
                    docs=results,
                    filter_used=True,
                    fallback_triggered=False,
                    reason=f"Filtered by {category} - found {len(results)} docs"
                )
            else:
                # Not enough results - FALLBACK
                all_results = await retrieve_all(question, top_k)
                return FilteringOutput(
                    docs=all_results,
                    filter_used=True,
                    fallback_triggered=True,
                    reason=f"Filter fallback: {category} had only {len(results)} docs, using all"
                )

        # Step 3: No category - retrieve all
        results = await retrieve_all(question, top_k)
        return FilteringOutput(
            docs=results,
            filter_used=False,
            fallback_triggered=False,
            reason="No category - searching all documents"
        )

    async def retrieve_by_category(
        self,
        question: str,
        category: str,
        top_k: int
    ) -> List[Document]:
        """Retrieve documents for specific category"""
        embedding = await get_embedding(question)
        return await search_documents(
            embedding,
            category_filter=category,
            top_k=top_k
        )

    async def retrieve_all(
        self,
        question: str,
        top_k: int
    ) -> List[Document]:
        """Retrieve from all documents"""
        embedding = await get_embedding(question)
        return await search_documents(
            embedding,
            category_filter=None,
            top_k=top_k
        )
```

#### 3.2.3 Реализовать `app/nodes/metadata_filtering/models.py`
**Содержит:**
```python
class FilteringOutput(BaseModel):
    docs: List[Document]           # Retrieved documents
    filter_used: bool              # Was filtering applied?
    fallback_triggered: bool       # Did we fallback to full search?
    reason: str                    # Explanation for logging
    category_docs_count: int       # Documents in category (if used)
    total_docs_searched: int       # Total documents in database
```

#### 3.2.4 Реализовать `app/nodes/metadata_filtering/node.py`
**Содержит:**
```python
@observe(as_type="span")
async def metadata_filter_node(state: Dict[str, Any]):
    """
    Metadata filtering node with safety mechanisms
    """
    question = state.get("question", "")
    category = state.get("category")
    category_confidence = state.get("category_confidence", 0.0)
    all_category_scores = state.get("all_category_scores", {})

    service = get_metadata_filtering_service()

    result = await service.filter_and_search(
        question=question,
        category=category,
        category_confidence=category_confidence,
        all_category_scores=all_category_scores,
        top_k=3
    )

    return {
        "docs": result.docs,
        "filter_used": result.filter_used,
        "fallback_triggered": result.fallback_triggered,
        "filtering_reason": result.reason
    }
```

#### 3.2.5 Обновить `app/storage/vector_store.py`
**Обновить функцию поиска:**
```python
async def search_documents(
    query_embedding: List[float],
    category_filter: Optional[str] = None,
    top_k: int = 3
) -> List[SearchResult]:
    """
    Search documents with optional category filtering
    """

    query = """
    SELECT content, 1 - (embedding <=> %s::vector) AS score, metadata
    FROM documents
    """

    params = [query_embedding]

    # Add category filter if provided
    if category_filter:
        query += "WHERE metadata->>'category' = %s"
        params.append(category_filter)

    query += "ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    async with get_async_db_connection() as conn:
        rows = await conn.execute(query, params)

        return [
            SearchResult(
                content=row[0],
                score=float(row[1]),
                metadata=row[2] or {}
            )
            for row in rows
        ]
```

#### 3.2.6 Обновить `app/pipeline/state.py`
**Добавить поля:**
```python
class State(TypedDict):
    # ... existing fields ...

    # NEW: Filtering results
    filter_used: Optional[bool]
    fallback_triggered: Optional[bool]
    filtering_reason: Optional[str]
```

#### 3.2.7 Обновить `app/pipeline/graph.py`
**Добавить node и edge:**
```python
from app.nodes.metadata_filtering.node import metadata_filter_node

workflow.add_node("metadata_filter", metadata_filter_node)

# After classification, before expand_query
workflow.add_edge("classify", "metadata_filter")
workflow.add_edge("metadata_filter", "expand_query")
```

#### 3.2.8 Создать `scripts/test_filtering.py`
**Для тестирования:**
- Для каждого question в dataset:
  - Run с filtering: метрики
  - Run без filtering: метрики
  - Сравнить recall, precision, latency
  - Подсчитать fallback rate
- Вывести: "Filtering улучшил recall на X%, fallback срабатывает Y% времени"

---

### ЗАДАЧА 3.3: Улучшить Routing Logic
**Время:** 1 день | **Приоритет:** 🟡 MEDIUM

#### 3.3.1 Обновить `app/nodes/routing/logic.py`
**Переписать decide_action:**
```python
def decide_action(
    generation_confidence: float,     # avg(faithfulness, relevancy)
    faithfulness_score: float,        # Grounded in context?
    intent_confidence: float,         # Classification confidence
    fallback_triggered: bool,         # Metadata filter fallback?
    threshold_auto_reply: float = 0.85,
    threshold_needs_review: float = 0.5
) -> Literal["auto_reply", "needs_review", "escalation"]:
    """
    Smart routing based on multiple confidence metrics
    """

    # If we had to fallback filtering - be very cautious
    if fallback_triggered:
        if generation_confidence > threshold_auto_reply:
            return "needs_review"  # Don't auto-reply if fallback
        else:
            return "escalation"

    # Normal routing based on generation quality
    if generation_confidence > threshold_auto_reply and faithfulness_score > 0.8:
        return "auto_reply"

    elif generation_confidence > threshold_needs_review:
        return "needs_review"

    else:
        return "escalation"
```

#### 3.3.2 Обновить `app/nodes/routing/node.py`
**Вычислить generation_confidence:**
```python
@observe(as_type="span")
async def route_node(state: Dict[str, Any]):
    """
    Improved routing node with multiple confidence metrics
    """
    faithfulness = state.get("faithfulness_score", 0.0)
    relevancy = state.get("relevancy_score", 0.0)
    intent_confidence = state.get("intent_confidence", 0.0)
    fallback_triggered = state.get("fallback_triggered", False)

    # Compute generation confidence as average
    generation_confidence = (faithfulness + relevancy) / 2

    action = decide_action(
        generation_confidence=generation_confidence,
        faithfulness_score=faithfulness,
        intent_confidence=intent_confidence,
        fallback_triggered=fallback_triggered
    )

    return {
        "action": action,
        "generation_confidence": generation_confidence,
        "faithfulness_score": faithfulness,
        "relevancy_score": relevancy
    }
```

#### 3.3.3 Обновить `app/pipeline/state.py`
**Добавить поля:**
```python
class State(TypedDict):
    # ... existing fields ...

    # NEW: Confidence scores
    generation_confidence: Optional[float]   # avg(faithfulness, relevancy)
    faithfulness_score: Optional[float]
    relevancy_score: Optional[float]
```

#### 3.3.4 Обновить `app/api/routes.py`
**Расширить `/ask` response:**
```python
@router.get("/ask")
@observe()
async def ask(q: str = Query(...)):
    result = await rag_graph.ainvoke({"question": q})

    return {
        "question": q,
        "answer": result.get("answer"),
        "action": result.get("action"),

        # NEW: Detailed scores
        "scores": {
            "intent_confidence": result.get("intent_confidence"),
            "category_confidence": result.get("category_confidence"),
            "generation_confidence": result.get("generation_confidence"),
            "faithfulness": result.get("faithfulness_score"),
            "relevancy": result.get("relevancy_score"),
        },

        # NEW: Filter info
        "filter_stats": {
            "filter_used": result.get("filter_used"),
            "fallback_triggered": result.get("fallback_triggered"),
            "reason": result.get("filtering_reason"),
        },

        # Existing
        "context": result.get("docs"),
        "matched_intent": result.get("intent"),
        "matched_category": result.get("category"),
    }
```

---

## 📊 TIMELINE & DEPENDENCIES

```
DAY 1-2: Task 3.1 (Classification)
  ├─ 3.1.1-3.1.9: Implement classifier + test
  └─ Update State & Graph

DAY 2-3: Task 3.2 (Metadata Filtering)
  ├─ 3.2.1-3.2.8: Implement filtering + test
  ├─ Update storage layer
  └─ Integration with graph

DAY 4: Task 3.3 (Routing Logic)
  ├─ 3.3.1-3.3.4: Improve routing
  ├─ Update API response
  └─ Integration testing

Total: ~4 days (can be done in parallel)
```

---

## 🔄 UPDATED GRAPH FLOW

```
START
  ↓
[classify_node] → intent, category, confidence
  ↓
[metadata_filter_node] → filtered docs, fallback info
  ↓
[expand_query_node] → query variants
  ↓
[hybrid_search_node] → vector + lexical search
  ↓
[rerank_node] → reranked docs
  ↓
[generate_node] → answer + metrics
  ↓
[route_node] → routing decision (auto_reply, needs_review, escalation)
  ↓
CONDITION:
├─ auto_reply → END
├─ needs_review → END (marked for review)
└─ escalation → END (marked for escalation)
```

---

## ✅ DEFINITION OF DONE

- ✅ Classification Node implemented (zero-shot BERT)
- ✅ Metadata Filtering with safety mechanisms
- ✅ Improved Routing Logic with multi-metric decision
- ✅ State updated with all new fields
- ✅ Graph updated with new nodes
- ✅ Storage layer supports category filtering
- ✅ API response includes all scores and stats
- ✅ All nodes logging to Langfuse
- ✅ Tests pass (classification, filtering, routing)
- ✅ Documentation updated
- ✅ Ready for next phase

---

## 📦 DEPENDENCIES TO ADD TO requirements.txt

```
# Classification
transformers>=4.30.0
torch>=2.0.0  # or use pytorch-cpu for lightweight

# Everything else should already be there
```

---

## 🚀 NEXT PHASES (After Phase 3)

### Phase 4: Advanced Features (optional)
- 4.1 Multi-Hop Reasoning
- 4.2 Conversation Memory
- 4.3 Feedback Loop Integration

### Phase 5: Production Hardening
- 5.1 Error handling & retry logic
- 5.2 Caching strategies (Redis)
- 5.3 Rate limiting
- 5.4 Performance optimization

---

## 📝 NOTES FOR IMPLEMENTATION

1. **Zero-shot BERT Details:**
   - Model: `facebook/bart-large-mnli` (~1.6GB)
   - Inference: ~150-200ms per question
   - Can be optimized with quantization if needed
   - Device: Auto-detect GPU, fallback to CPU

2. **Safety First:**
   - Always log filtering decisions
   - Monitor fallback rate weekly
   - If fallback > 30%, need to retrain classifier
   - Add alerts for classification failures

3. **Caching Strategy:**
   - Cache classification results (per question)
   - Use simple LRU cache initially
   - Consider Redis for distributed caching later

4. **Testing:**
   - Manual test with 10-20 questions
   - Automated test with full dataset
   - Compare metrics before/after Phase 3

5. **Documentation:**
   - Add example curl requests
   - Document confidence thresholds
   - Explain fallback behavior
