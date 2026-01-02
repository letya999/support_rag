# PHASE 4 - OPTIONAL ADVANCED RETRIEVAL NODES (План без кода)

Дополнительные узлы для улучшения retrieval после Фазы 3.

---

## 🎯 NODE 4.1: Multi-Hop Reasoning (Сложные вопросы)

**Purpose:** Для многоуровневых вопросов найти цепочку связанных документов.

**Example:**
```
User: "Как вернуть товар, если он был доставлен с повреждениями?"

Без Multi-Hop:
- Retrieve: "Return policy" документ
- Generate: неполный ответ (не учитывает process доставки)

С Multi-Hop:
- Retrieve: "Return policy" (1st doc)
  → Find related: "Delivery process" (2nd doc)
  → Find related: "Damage claims" (3rd doc)
- Generate: полный ответ с контекстом всех 3 документов
```

**What to do:**

1. **Complexity Detection:**
   - Анализировать вопрос на сложность
   - Метрики: количество ключевых слов, длина вопроса, наличие "и", "если", "после"
   - Threshold: complexity_score > 0.6 → use multi-hop

2. **Hop Logic:**
   - Step 1: Retrieve top-1 document для основного вопроса
   - Step 2: Extract keywords/entities из retrieved document
   - Step 3: Find related documents (через metadata links или semantic similarity)
   - Step 4: Combine все документы в один контекст (с indication где какой doc)

3. **Implementation details:**
   - Create: `app/nodes/multihop/node.py`
   - Create: `app/nodes/multihop/complexity_detector.py` - вычисление complexity_score
   - Create: `app/nodes/multihop/hop_resolver.py` - логика поиска связанных docs
   - Update: `app/pipeline/state.py` - add `complexity_score`, `hops_used`
   - Update: `app/pipeline/graph.py` - conditional: if complexity_score > 0.6 → use multihop

4. **Integration in graph:**
   ```
   ... → retrieve → [complexity_check] →
                        ├─ complex (>0.6) → multihop → merge_docs
                        └─ simple (≤0.6) → skip
                                           ↓
                                         route → ...
   ```

5. **Testing:**
   - Test on complex questions (with multiple entities)
   - Verify no infinite loops in hop resolution
   - Check latency doesn't increase too much

---

## 🎯 NODE 4.2: Query Reformulation (Улучшить поиск)

**Purpose:** Переформулировать вопрос для лучшего поиска (учитывая domain-specific синонимы).

**Example:**
```
User: "Сколько стоит доставка?"

Without Reformulation:
- Search: "сколько стоит доставка" → может не найти docs с "shipping cost"

With Reformulation:
- Original: "сколько стоит доставка"
- Reformulations:
  1. "shipping cost"
  2. "delivery price"
  3. "shipping fee"
- Search by each variant → объединить результаты
```

**What to do:**

1. **Reformulation Strategy:**
   - Using LLM (gpt-4o-mini) to generate 2-3 reformulations
   - Include synonyms specific to domain (billing, shipping, etc.)
   - Reformulations should be shorter, more keyword-focused

2. **Implementation:**
   - Create: `app/nodes/query_reformulation/node.py`
   - Create: `app/nodes/query_reformulation/reformulator.py`
   - Prompt template: "Generate 2-3 alternative phrasings of this question, focusing on key terms used in technical documentation"

3. **Integration:**
   - Run AFTER classification (uses intent/category info for better reformulations)
   - Generate reformulations in parallel
   - Each reformulation searched separately
   - Combine results (deduplicate, merge scores)

4. **Update State:**
   - Add: `query_reformulations: List[str]`

5. **Update Graph:**
   ```
   classify → metadata_filter → [reformulate] → retrieve (for each variant)
                                    ↓
                              [fusion] → rerank
   ```

---

## 🎯 NODE 4.3: Semantic Clustering (Группировка похожих результатов)

**Purpose:** Группировать похожие результаты в один кластер для лучшей организации контекста.

**Example:**
```
Without Clustering:
Retrieved docs:
1. "Return policy section 1"
2. "Return policy section 2"
3. "Shipping policy"

Result: 3 separate docs, some redundant

With Clustering:
Cluster 1 (Return Policy): docs 1, 2
Cluster 2 (Shipping): doc 3

Result: organized, easier for generation, less redundancy
```

**What to do:**

1. **Clustering Algorithm:**
   - Use embedding similarity to cluster documents
   - Threshold for "similar": cosine_similarity > 0.7
   - Group documents by semantic similarity

2. **Implementation:**
   - Create: `app/nodes/clustering/node.py`
   - Create: `app/nodes/clustering/clusterer.py` - clustering logic
   - Use: sklearn.cluster.AgglomerativeClustering or simple threshold-based grouping

3. **Output:**
   - Return clustered docs with cluster_id
   - Top doc from each cluster prioritized
   - Information about cluster cohesion (for logging)

4. **Integration:**
   ```
   ... → rerank → [clustering] → generate
   ```
   - After reranking (so best docs are from best clusters)
   - Pass cluster info to generation for better context organization

5. **Benefits:**
   - Reduces redundancy in context
   - Better organization for generation
   - Can help with long contexts (select 1 doc per cluster)

---

## 🎯 NODE 4.4: Cross-Reference Resolution (Связи между документами)

**Purpose:** Находить документы, на которые ссылаются другие документы (через metadata links).

**Example:**
```
Retrieved doc: "FAQ - Return Process"
  metadata.see_also: ["Return Policy", "Shipping", "Damage Claims"]

Action:
- Retrieve linked documents
- Add to context with note: "(related: Return Policy)"
- Helps generate more complete answers
```

**What to do:**

1. **Link Extraction:**
   - Parse metadata.see_also, metadata.related_topics, etc.
   - Can be array of doc_ids or doc_titles

2. **Link Resolution:**
   - For each link: retrieve linked document
   - Limit to 1-2 links per doc (avoid explosion)
   - Check for circular references

3. **Implementation:**
   - Create: `app/nodes/cross_reference/node.py`
   - Create: `app/nodes/cross_reference/link_resolver.py`
   - Update: documents schema to include `see_also: List[str]` in metadata

4. **Integration:**
   ```
   ... → rerank → [cross_reference] → generate
   ```
   - After reranking (limit links from top-k docs only)
   - Mark linked docs differently in context

5. **Data requirement:**
   - Documents need metadata.see_also populated during ingestion
   - Can be created manually or extracted from original documentation

---

## 📊 SUMMARY: Which nodes to implement?

| Node | Complexity | Impact | Priority | Estimated Time |
|------|-----------|--------|----------|-----------------|
| Multi-Hop | High | Medium | 🟡 Medium | 2-3 days |
| Query Reformulation | Medium | High | 🟡 Medium | 1-2 days |
| Semantic Clustering | Low | Low | 🟢 Low | 1 day |
| Cross-Reference | Low | Medium | 🟢 Low | 1 day |

**Recommendation:**
1. Start with **Query Reformulation** (high impact, medium effort)
2. Then **Multi-Hop Reasoning** (complex questions need this)
3. Optional: **Cross-Reference** (if metadata available)
4. Optional: **Semantic Clustering** (nice-to-have for UX)

---

## 🔄 UPDATED GRAPH WITH ALL NODES (Phase 3 + Phase 4)

```
START
  ↓
[classify] → intent, category
  ↓
[metadata_filter] → filtered docs (with fallback)
  ↓
[reformulate] (Phase 4) → multiple query variants
  ↓
[retrieve] → retrieve for each variant (parallel)
  ↓
[fusion] → combine results
  ↓
[rerank] → cross-encoder reranking
  ↓
[clustering] (Phase 4) → group similar docs
  ↓
[cross_reference] (Phase 4) → resolve linked docs
  ↓
[multihop] (Phase 4, conditional) → find related docs if complex
  ↓
[merge_context] → combine all docs into final context
  ↓
[generate] → LLM generation with full context
  ↓
[route] → decision based on scores
  ↓
CONDITION:
├─ auto_reply → END
├─ needs_review → END
└─ escalation → END
```

---

## ⏱️ Timeline Estimate

**Phase 3:** ~4 days (Done ✅)
**Phase 4 Optional:**
- Query Reformulation: 1-2 days
- Multi-Hop Reasoning: 2-3 days
- Cross-Reference: 1 day
- Clustering: 1 day
- **Total Phase 4:** 5-7 days (or selective: pick 1-2 nodes)

**Total project:** Phase 1-3 (~1 week) + Phase 4 optional (~1 week) = **2-3 weeks for full MVP**

---

## ✅ What success looks like after Phase 4

**Before Phase 3:**
- Vector search only
- Simple confidence routing
- Low precision/recall

**After Phase 3:**
- Classification-aware retrieval
- Safety fallback for filtering
- Multi-metric routing
- ~30-40% improvement in retrieval quality

**After Phase 4 (if implemented):**
- Handle complex, multi-hop questions
- Better query understanding (reformulation)
- Organized context (clustering)
- Cross-document references
- ~50-60% improvement over baseline
- Production-ready for most support queries
