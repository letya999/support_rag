# PHASE 4 LIGHTWEIGHT - RULE-BASED & DOMAIN-SPECIFIC NODES (План)

Легкие узлы без LLM для улучшения retrieval на основе домена, синонимов и правил.

---

## 🎯 NODE 4.5: Synonym/Alias Expansion (Синонимы и алиасы)

**Purpose:** Расширить вопрос синонимами из предопределенного словаря (легко + быстро).

**Example:**
```
Domain: E-commerce Support

User question: "Как вернуть товар?"

Synonym mapping:
- "return" → ["refund", "exchange", "send back", "return"]
- "товар" → ["product", "item", "order", "purchase"]
- "вернуть" → ["get money back", "exchange", "refund"]

Result:
- Original: "Как вернуть товар?"
- Expanded variants:
  1. "How to refund product?"
  2. "How to exchange item?"
  3. "How to send back order?"

Search each variant → better recall
```

**What to do:**

1. **Create domain-specific dictionary:**
   - File: `app/nodes/synonym_expansion/synonyms.yaml` или `.json`
   - Structure:
     ```yaml
     refund:
       - return
       - send back
       - money back
       - refund request

     product:
       - item
       - purchase
       - order
       - good
       - merchandise

     damaged:
       - broken
       - defective
       - not working
       - damaged in transit
     ```

2. **Implementation:**
   - Create: `app/nodes/synonym_expansion/node.py`
   - Create: `app/nodes/synonym_expansion/expander.py`
   - Logic: find keywords in question → replace with synonyms → generate variants
   - Use: regex or simple keyword matching

3. **Integration:**
   ```
   classify → metadata_filter → [synonym_expansion] → retrieve
   ```
   - After classification (know domain/intent)
   - Before retrieve (use expanded variants)

4. **Advantages:**
   - ✅ Fast (no LLM, just dictionary lookup)
   - ✅ Deterministic (same question = same variants)
   - ✅ Easy to customize per domain
   - ✅ No external API calls
   - ❌ Limited by predefined synonyms

5. **Effort:** 1 day | **Impact:** High (especially for support domain)

---

## 🎯 NODE 4.6: Domain-Specific Rule-Based Reformulation (Правила домена)

**Purpose:** Переформулировать вопрос на основе regex/pattern-based правил (специфично для продукта).

**Example:**
```
Domain: SaaS Support (Slack, Jira, etc)

Rules:
1. Pattern: "How to [ACTION]"
   → Add: "[ACTION] guide", "[ACTION] tutorial", "setup [ACTION]"

2. Pattern: "error: [ERROR_CODE]"
   → Search: error code documentation, troubleshooting guide

3. Pattern: "[FEATURE_NAME] not working"
   → Search: "[FEATURE_NAME]" + "troubleshooting" + "debug"

4. Pattern: "integration with [TOOL]"
   → Search: "integration", "API", "[TOOL]", "setup"

User question: "How to configure webhooks?"
Applied rules:
- Rule 1 (How to): add "webhook guide", "webhook tutorial", "setup webhooks"
- Result variants:
  1. "configure webhooks"
  2. "webhook guide"
  3. "webhook tutorial"
  4. "setup webhooks"
```

**What to do:**

1. **Define domain-specific rules:**
   - File: `app/nodes/rule_reformulation/rules.yaml`
   - Structure:
     ```yaml
     rules:
       - pattern: "(?:How to|how do I|can I) (.+?)?"
         action: add_terms
         terms: ["guide", "tutorial", "step by step"]

       - pattern: "error: (.+)"
         action: add_terms
         terms: ["troubleshooting", "fix", "solution"]

       - pattern: "(.+?) not working"
         action: expand
         expansion: "{keyword} troubleshooting, {keyword} debug, {keyword} issue"

       - pattern: "integration with (.+)"
         action: expand
         expansion: "integrate {keyword}, {keyword} API, setup {keyword}"
     ```

2. **Implementation:**
   - Create: `app/nodes/rule_reformulation/node.py`
   - Create: `app/nodes/rule_reformulation/rule_engine.py`
   - Use: regex pattern matching + action execution
   - Language: can be domain-specific (EN/RU/etc)

3. **Action types:**
   - `add_terms` - добавить термины в конец
   - `expand` - заменить по шаблону
   - `replace` - заменить по правилу
   - `duplicate` - дублировать с вариантом

4. **Integration:**
   ```
   classify → metadata_filter → [synonym_expansion] → [rule_reformulation] → retrieve
   ```
   - Chain both reformulations (synonyms + rules)
   - Generate product of all variants

5. **Advantages:**
   - ✅ Super fast (just regex)
   - ✅ Explainable (can see which rule fired)
   - ✅ No training needed
   - ✅ Easy to debug and update
   - ❌ Needs domain expert to write rules

6. **Effort:** 1-2 дня | **Impact:** High

---

## 🎯 NODE 4.7: Product-Specific Slang Normalizer (Сленг продукта)

**Purpose:** Преобразовать пользовательский сленг в стандартные термины.

**Example:**
```
Domain: Support for product "DataFlow" (ETL platform)

Slang mapping:
- "pipe" → "pipeline"
- "DAG" → "directed acyclic graph"
- "schedule" → "task schedule"
- "log viewer" → "execution logs"
- "rejectable" → "failed records"
- "sync" → "data sync"
- "transformation" → "data transformation"

User: "My pipe keeps rejecting records on schedule"
→ Normalized: "My pipeline keeps rejecting records on task schedule"
→ Better search results!
```

**What to do:**

1. **Create slang dictionary:**
   - File: `app/nodes/slang_normalizer/slang_mappings.yaml`
   - Structure:
     ```yaml
     slang_terms:
       pipe: pipeline
       dag: directed acyclic graph
       rejectable: rejected records
       log viewer: execution logs
       cron: scheduled task
       ETL: extract transform load

     # Can also be context-specific
     context_slang:
       billing:
         invoice: bill
         payment: transaction
       support:
         ticket: support request
         help: assistance
     ```

2. **Implementation:**
   - Create: `app/nodes/slang_normalizer/node.py`
   - Create: `app/nodes/slang_normalizer/normalizer.py`
   - Use: simple string replacement (word-level to avoid substring issues)
   - Case-insensitive matching

3. **Integration:**
   ```
   classify → [slang_normalizer] → metadata_filter → [synonyms] → retrieve
   ```
   - Very early in pipeline (normalize before everything else)
   - Quick preprocessing step

4. **Advantages:**
   - ✅ Fast
   - ✅ Handles product-specific terminology
   - ✅ Improves recall for users using slang
   - ❌ Needs domain knowledge to build

5. **Effort:** 0.5 day | **Impact:** Medium (depends on slang usage)

---

## 🎯 NODE 4.8: Intent-Aware Synonym Mapper (Синонимы зависимые от intent)

**Purpose:** Использовать разные синонимы в зависимости от intent/category.

**Example:**
```
Domain: E-commerce

Same word, different intent:
- "order" (intent=billing) → ["invoice", "transaction", "purchase"]
- "order" (intent=shipping) → ["shipment", "package", "delivery"]
- "order" (intent=returns) → ["return request", "refund request"]

User: "Where is my order?"
Context: previously asked about billing
→ Use billing synonyms: invoice, transaction, payment status
→ Better results!
```

**What to do:**

1. **Create intent-aware mappings:**
   - File: `app/nodes/intent_aware_synonyms/mappings.yaml`
   - Structure:
     ```yaml
     billing:
       synonyms:
         order: [invoice, transaction, purchase, payment]
         return: [refund, money back, reimbursement]
         price: [cost, fee, amount, charge]

     shipping:
       synonyms:
         order: [shipment, package, delivery, shipment]
         return: [send back, return shipment, reverse logistics]
         address: [shipping address, destination, location]

     support:
       synonyms:
         issue: [problem, error, bug, defect]
         help: [assistance, support, guide]
     ```

2. **Implementation:**
   - Create: `app/nodes/intent_aware_synonyms/node.py`
   - Use: classification result to choose right synonym set
   - Then apply expansions

3. **Integration:**
   ```
   classify → [intent_aware_synonyms] → retrieve
   ```
   - Right after classification (have intent/category)
   - Before synonym expansion

4. **Advantages:**
   - ✅ Context-aware
   - ✅ Better accuracy than generic synonyms
   - ❌ More complex mapping to maintain

5. **Effort:** 1 day | **Impact:** High

---

## 🎯 NODE 4.9: Typo/Spelling Correction (Исправление опечаток)

**Purpose:** Исправить опечатки в вопросе перед поиском.

**Example:**
```
User: "How to configer payment method?"
Error: typo "configer" instead of "configure"

Correction: "How to configure payment method?"
Better: finds right docs about "configure", not "configer"
```

**What to do:**

1. **Implementation options:**
   - Option A: Use `pyspellchecker` or `autocorrect` library (simple)
   - Option B: Use domain-specific spell checker (better)
   - Option C: Levenshtein distance for known terms (lightweight)

2. **Approach:**
   - Create: `app/nodes/spelling_correction/node.py`
   - Use: pre-trained spell checker or simple library
   - Compare with known domain terms (from documents)

3. **Integration:**
   ```
   [slang_normalizer] → [spelling_correction] → metadata_filter
   ```
   - Early in pipeline
   - Quick preprocessing

4. **Advantages:**
   - ✅ Handles typos (common in support)
   - ✅ Improves recall
   - ⚠️ Can sometimes overcorrect

5. **Effort:** 0.5 day | **Impact:** Low-Medium

---

## 📊 COMPARISON: LLM vs Rule-Based

| Feature | LLM Reformulation (4.2) | Rule-Based (4.5-4.9) |
|---------|----------------------|-------------------|
| **Speed** | Slow (API call) | ⚡ Fast |
| **Cost** | 💰 Per request | Free |
| **Flexibility** | Very high | Limited to rules |
| **Explainability** | Black box | Clear rules |
| **Training** | No | Need domain expert |
| **Accuracy** | High (domain-agnostic) | Very high (domain-specific) |
| **Best for** | General Q&A | Domain-specific support |

---

## 🎯 RECOMMENDED ORDER FOR PHASE 4

**Quick Wins (1-2 days):**
1. ✅ Slang Normalizer (4.7) - 0.5 day
2. ✅ Spelling Correction (4.9) - 0.5 day
3. ✅ Synonym Expansion (4.5) - 1 day

**Medium Effort (1-2 days):**
4. ✅ Rule-Based Reformulation (4.6) - 1-2 days
5. ✅ Intent-Aware Synonyms (4.8) - 1 day

**Advanced (1-3 days):**
6. ⚙️ Query Reformulation with LLM (4.2) - 1-2 days
7. ⚙️ Multi-Hop Reasoning (4.1) - 2-3 days
8. ⚙️ Cross-Reference Resolution (4.4) - 1 day
9. ⚙️ Semantic Clustering (4.3) - 1 day

---

## 🔄 COMPLETE PIPELINE WITH ALL NODES

```
START
  ↓
[slang_normalizer] → "configer" → "configure"
  ↓
[spelling_correction] → fix typos
  ↓
[classify] → intent, category
  ↓
[intent_aware_synonyms] → context-specific synonyms
  ↓
[synonym_expansion] → expand query with synonyms
  ↓
[rule_reformulation] → apply domain rules
  ↓
[metadata_filter] → filter by category
  ↓
[retrieve] → retrieve docs (with multiple variants)
  ↓
[fusion] → combine results
  ↓
[rerank] → cross-encoder reranking
  ↓
[clustering] → group similar docs
  ↓
[cross_reference] → resolve linked docs
  ↓
[multihop] → find related docs if complex
  ↓
[merge_context] → combine into final context
  ↓
[generate] → LLM generation
  ↓
[route] → decision
  ↓
END
```

---

## ✅ PROS OF RULE-BASED APPROACH

1. **Fast** - no API calls, instant processing
2. **Cheap** - free, no LLM costs
3. **Deterministic** - same input = same output
4. **Explainable** - can see exactly what happened
5. **Customizable** - easy to add domain rules
6. **Debuggable** - easy to test and fix
7. **No hallucinations** - just rule-based replacements

---

## ⏱️ EFFORT SUMMARY

| Node | Type | Effort | Impact | Days |
|------|------|--------|--------|------|
| 4.5 Synonyms | Rule | Easy | High | 1 |
| 4.6 Rule Reformulation | Rule | Medium | High | 1-2 |
| 4.7 Slang Normalizer | Rule | Easy | Medium | 0.5 |
| 4.8 Intent-Aware Synonyms | Rule | Medium | High | 1 |
| 4.9 Spelling Correction | Rule | Easy | Medium | 0.5 |
| 4.2 LLM Reformulation | LLM | Medium | High | 1-2 |
| 4.1 Multi-Hop | Advanced | Hard | Medium | 2-3 |
| 4.4 Cross-Reference | Advanced | Easy | Medium | 1 |
| 4.3 Clustering | Advanced | Medium | Low | 1 |

---

## 🎯 RECOMMENDATION FOR YOUR PROJECT

**For Support RAG (recommended):**

Phase 3: Done ✅

Phase 4 - Choose either:

**Option A: Production-Ready (5-6 days)**
- 4.7 Slang Normalizer (0.5 day)
- 4.9 Spelling Correction (0.5 day)
- 4.5 Synonym Expansion (1 day)
- 4.6 Rule Reformulation (2 days)
- 4.8 Intent-Aware Synonyms (1 day)

Result: Fast, cheap, super-optimized for domain

**Option B: Full-Featured (7-9 days)**
- All from Option A (5-6 days)
- 4.2 LLM Reformulation (1-2 days)
- 4.1 Multi-Hop Reasoning (2-3 days)

Result: Handles everything, but slower/more expensive

**My recommendation:** Start with **Option A** (rule-based), then add **4.2 LLM Reformulation** if needed.
