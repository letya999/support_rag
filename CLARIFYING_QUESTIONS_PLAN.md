# Clarifying Questions Flow — Implementation Plan

## Overview

Implement a multi-turn dialogue flow for collecting clarifying information from users before generating final answers. This allows the system to ask targeted questions (payment method, issue date, device type, etc.) when needed to provide accurate, context-specific support.

**Status:** MVP (Phase 1)
**Complexity:** Low (~100 lines of code, 4 changes)

---

## Architecture

### Current State
- Linear flow: question → classification → retrieval → generation → answer
- No mechanism to collect structured information mid-flow
- Cannot ask follow-up questions before answering

### Target State
- Non-linear flow: question → classification → retrieval → **[clarification if needed]** → generation → answer
- Ability to ask questions and collect answers from users
- Loop until all clarifying questions are answered
- Then generate final answer with full context

---

## Implementation Plan

### **Step 1: Extend State** ✅

**File:** `app/pipeline/state.py`

**Change:** Add one field to the State TypedDict

```python
collected_slots: Annotated[Optional[Dict[str, str]], overwrite]
```

**Why:** Store user answers to clarifying questions. Format: `{question: user_answer}`

**Lines changed:** 1

---

### **Step 2: Modify Retrieval Node** ✅

**File:** `app/nodes/hybrid_search/node.py` (or wherever retrieval is)

**Change:** After retrieving best document, check if clarifying questions exist

```python
# Pseudo-code
if best_doc_metadata.get("clarifying_questions"):
    state["dialog_state"] = "NEEDS_CLARIFICATION"
else:
    state["dialog_state"] = "ANSWER_PROVIDED"
```

**Why:** Inform the graph that clarification is needed before proceeding to generation.

**Lines changed:** 5-10

---

### **Step 3: Create Clarification Questions Node** ✅

**File:** `app/nodes/clarification_questions/node.py` (NEW)

**Responsibility:** Handle multi-turn clarification dialogue

#### Logic

**First Invocation** (when `dialog_state == "NEEDS_CLARIFICATION"` and `collected_slots == {}`)
1. Extract `clarifying_questions` array from `best_doc_metadata`
2. Format as user-friendly questions: `"1. Payment method?\n2. When did you pay?"`
3. Return as `answer` (display to user)
4. Leave `dialog_state` as `"NEEDS_CLARIFICATION"`

**Subsequent Invocations** (new user message received)
1. Extract latest user message from `conversation_history`
2. Parse answers by order (split by punctuation/newlines)
3. Map answers to questions positionally
4. Update `collected_slots`: `{"Question 1": "answer1", "Question 2": "answer2"}`
5. Check: Did user answer ALL questions?
   - **If NO:** Return next questions or ask for clarification → loop continues
   - **If YES:** Set `dialog_state = "ANSWER_PROVIDED"` → exit loop

#### Input Contract

```python
INPUT_CONTRACT = {
    "required": ["best_doc_metadata", "conversation_history"],
    "optional": ["collected_slots"]
}
```

#### Output Contract

```python
OUTPUT_CONTRACT = {
    "guaranteed": ["answer", "collected_slots"],
    "conditional": ["dialog_state"]  # Set to ANSWER_PROVIDED when done
}
```

#### Key Implementation Details

- Use simple positional parsing initially (split by newlines/commas)
- Don't validate answers — accept as-is (upgrade in Phase 2)
- If user didn't answer one question → ask again
- Store conversation history for context (loop tracking)

**Lines:** ~80-100

---

### **Step 4: Add Conditional Routing in LangGraph** ✅

**File:** `app/pipeline/graph_builder.py` (or wherever graph is built)

**Change:** Add conditional edges after retrieval

```python
def route_after_retrieval(state):
    """Route to clarification if needed, else to generation."""
    if state.get("dialog_state") == "NEEDS_CLARIFICATION":
        return "clarification_questions"
    else:
        return "prompt_routing"

graph.add_conditional_edges(
    "retrieval",
    route_after_retrieval,
    {
        "clarification_questions": "clarification_questions",
        "prompt_routing": "prompt_routing"
    }
)

# After clarification: proceed to prompt_routing
# (clarification_node sets dialog_state = ANSWER_PROVIDED when done)
graph.add_edge("clarification_questions", "prompt_routing")
```

**Why:** Control flow routing based on whether clarification is needed.

**Lines:** ~15

---

### **Step 5: Update Data** (Parallel with code)

**File:** `datasets/qa_data_extended.json`

**Change:** Add clarifying questions to relevant FAQ entries

```json
{
  "id": "payment_issue_123",
  "question": "Why was my payment declined?",
  "metadata": {
    "category": "payment",
    "clarifying_questions": [
      "What payment method did you use?",
      "When did you attempt payment?",
      "What error message did you see?"
    ]
  }
}
```

**Which entries need this?**
- `payment` issues → need: payment method, date, error
- `technical_issue` → need: device, OS, error message
- `account_recovery` → need: email, account ID, when issue started
- `subscription` → need: plan type, when issue started
- `refund` → need: order ID, reason, when refund needed

**Which entries DON'T need this?**
- General info (FAQ, how-to, documentation references)
- Entries already detailed enough with just the question

**Estimate:** 20-30 entries affected

---

## Message Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    INITIAL REQUEST                      │
│            User: "Problem with my payment"              │
└────────────────────────┬────────────────────────────────┘
                         │
                    [Classification]
                    category: payment
                         │
                    [Retrieval]
        best_doc has: clarifying_questions
                         │
         ┌───────────────┴────────────────┐
         │ dialog_state = NEEDS_CLARIF.   │
         └───────────────┬────────────────┘
                         │
            ┌────────────▼──────────────┐
            │  CLARIFICATION NODE (1st) │
            │   collected_slots: {}     │
            │  Collect all questions    │
            └────────────┬───────────────┘
                         │
        System: "1. Payment method?
                 2. When did you pay?
                 3. Error message?"
                         │
        ┌────────────────┴──────────────────┐
        │     USER PROVIDES ANSWERS         │
        │     "Card, yesterday, code 402"   │
        └────────────────┬──────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │  CLARIFICATION NODE (2nd call) │
         │  Parse conversation_history    │
         │  Update collected_slots        │
         │  All questions answered? YES   │
         │  Set: dialog_state = ANSWERED  │
         └───────────────┬────────────────┘
                         │
                  [Prompt Routing]
            (with collected_slots context)
                         │
                   [Generation]
            "For card payments on [date],
             error 402 means..."
                         │
            ┌────────────▼──────────────┐
            │    FINAL ANSWER TO USER   │
            └───────────────────────────┘
```

---

## Loop Mechanics

The loop works through LangGraph's request-response cycle:

1. **First request:** User sends "Problem with payment"
   - Graph processes: classification → retrieval → needs clarification → clarification_node (1st call) → return questions

2. **Second request:** User sends "Card, yesterday, code 402"
   - LangGraph receives new user message in same session
   - conversation_history is updated with both messages
   - Graph processes again: classification → retrieval → needs clarification → clarification_node (2nd call)
   - Clarification_node parses the conversation_history, extracts answers, checks if complete
   - If complete: sets dialog_state = "ANSWER_PROVIDED", proceeds to generation

3. **Subsequent requests:** If user didn't answer all questions
   - Same flow, clarification_node returns more questions
   - Loop continues until all answers collected

---

## YAGNI Check

| Feature | Included? | Reason |
|---------|-----------|--------|
| `collected_slots` in state | ✅ YES | Must store answers for generation context |
| Separate clarification node | ✅ YES | Needs multi-turn loop logic & parsing |
| Conditional edge routing | ✅ YES | Otherwise always goes to generation |
| `required_slots` field | ❌ NO | ALL questions are mandatory (order = priority) |
| `optional_slots` field | ❌ NO | Unnecessary, defer to Phase 2 |
| `dialogue_phase` in state | ❌ NO | Duplicates `dialog_state` from state machine |
| `slot_discovery_node` | ❌ NO | Overkill — 5 lines in retrieval sufficient |
| Query enrichment | ❌ NO | Phase 2 optimization |
| Fallback/retry logic | ❌ NO | Phase 2 robustness |
| LLM-based parsing | ❌ NO | Phase 2 sophistication (positional parsing v1) |

---

## Changes Summary

| File | Type | LOC | Risk |
|------|------|-----|------|
| `state.py` | Modify | +1 | Very Low |
| `retrieval_node.py` | Modify | +5 | Very Low |
| `clarification_questions_node.py` | **NEW** | ~100 | Low |
| `graph_builder.py` | Modify | +15 | Low |
| `qa_data_extended.json` | Update | +N | Very Low |

**Total code:** ~120 lines new/modified

---

## Phase 2 (Future Enhancements)

These are deliberately excluded from Phase 1 MVP:

- **Smart parsing:** Use LLM NER to extract answers from unstructured text
- **Query enrichment:** Enrich original query with collected_slots before re-retrieval
- **Fallback logic:** Retry if user doesn't answer; escalate if stuck
- **Validation:** Validate answer types (email format, date parsing, etc.)
- **Optional questions:** Support non-mandatory follow-ups based on answers
- **Context memory:** Remember slots across sessions
- **Metrics:** Track clarification rates, completion rates, user satisfaction
- **Localization:** Multi-language support for questions

---

## Testing Strategy (Phase 1)

### Unit Tests
- `test_clarification_node_parsing.py` — verify answer parsing logic
- `test_state_transitions.py` — verify dialog_state transitions

### Integration Tests
- Test full flow: question → clarification → answer
- Test multi-turn loop (same user, multiple messages)
- Test when no clarification needed (skip loop)

### Manual Testing
- Support ticket scenario: payment issue with clarifications
- Technical issue scenario: device/OS/error questions
- Edge case: user provides all answers in one message

---

## Rollout Plan

1. **Implement Steps 1-4 (code changes)**
2. **Prepare data (Step 5 — add clarifying questions to 20-30 entries)**
3. **Unit + integration test**
4. **Staging environment test with 10% of messages**
5. **Monitor: clarification request rate, completion rate**
6. **Production rollout (100%)**

---

## Success Metrics (Phase 1 MVP)

- ✅ System correctly identifies when clarification needed
- ✅ Multi-turn dialogue works (loop collects answers)
- ✅ All required questions answered before generation
- ✅ Generated answer uses collected_slots context
- ✅ No regressions in non-clarification scenarios

---

## Notes

- **Backward compatibility:** Old entries without `clarifying_questions` in metadata → skip clarification entirely
- **Session persistence:** Dialog state and conversation_history preserved across user requests (LangGraph's default)
- **Language support:** Questions inherit language from `detected_language` (prompt_routing will format them)
- **Escalation:** If loop repeats >3 times → Phase 2 (escalate to human)

---

## References

- State machine: `app/nodes/state_machine/states_config.py`
- Current states: `INITIAL`, `ANSWER_PROVIDED`, `AWAITING_CLARIFICATION`, `ESCALATION_NEEDED`, etc.
- LangGraph patterns: `app/pipeline/graph_builder.py`
- Data format: `datasets/qa_data_extended.json`
