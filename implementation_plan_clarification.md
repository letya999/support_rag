# Implementation Plan: Clarification Loop Refactoring

This plan details the architectural changes required to implement a robust, stateful clarification flow that strictly adheres to the "1 question - 1 answer" paradigm and prevents search hallucinations during the clarification phase.

## 1. Problem Analysis & Proposed Solution

### The Issues
1.  **Search Hallucination:** When the user answers a clarification question (e.g., "12"), the current system treats it as a new search query, re-triggering retrieval. This leads to irrelevant search results ("Technical Issue") because "12" is semantically weak.
2.  **State Fragility:** The system attempts to dynamically determine if it should "Ask" or "Parse" based on message history, which is error-prone. It lacks a rigid "Clarification Mode".
3.  **Handoff Timing:** Currently, the system escalates immediately upon failure. The requirement is to generating a helpful answer *using* the gathered details, and *then* escalate if the intent requires human intervention.

### The Solution: "Clarification Loop Mode"
We will implement a **Dedicated State Loop** that bypasses the Search/Retrieval subsystem entirely when active.

**Sequence:**
1.  **Trigger:** `HybridSearch` finds a doc with `clarifying_questions`.
2.  **Enter Mode:** System initializes a `ClarificationContext` (Queue of questions).
3.  **Strict Loop:**
    *   **User Turn:** User inputs text.
    *   **Router:** Detects `ClarificationContext.active=True`. **SKIPS SEARCH**. Routes directly to `ClarificationNode`.
    *   **Node:** Saves answer -> Advances Index -> Asks Next Question OR Exits.
4.  **Exit & Generate:** Once all questions are answered, the system proceeds to `PromptRouting` -> `Generation` using the accumulated context.
5.  **Soft Handoff:** If the original document required handoff, the system generates the answer *first*, and *then* marks the session for escalation.

---

## 2. Data Modeling Changes

### 2.1. `app/pipeline/state.py`
Add a dedicated TypedDict for the clarification context.

```python
class ClarificationContext(TypedDict):
    active: bool                # Is the loop active?
    questions: List[str]        # Strict ordered list from metadata
    current_index: int          # Pointer to the current question
    answers: Dict[str, str]     # Collected { "Question": "User Answer" }
    original_doc_content: str   # To avoid re-fetching the doc later
    requires_handoff: bool      # If True, escalate AFTER generation
```

Update the main `State` to include `clarification_context`.

### 2.2. `app/services/cache/models.py`
Update `UserSession` to persist this context in Redis. This ensures the state survives the request/response cycle.

```python
class UserSession(BaseModel):
    # ... existing fields ...
    clarification_context: Optional[dict] = None
```

### 2.3. Node Persistence
*   **`SessionStarter`**: Must load `clarification_context` from `UserSession` into the graph `State`.
*   **`ArchiveSession`**: Must save `state["clarification_context"]` back to `UserSession` at the end of the run.

---

## 3. Graph Topology Changes (`app/pipeline/graph_builder.py`)

This is the most critical change to prevent the "Search on '12'" bug.

### Current Flow
`Start` -> `Guardrails` -> `CheckCache` -> `HybridSearch` ...

### New Flow
`Start` -> `Guardrails` -> **`ClarificationRouter` (Conditional Edge)**

**Logic for Conditional Edge:**
```python
def route_after_guardrails(state: State) -> str:
    ctx = state.get("clarification_context", {})
    if ctx and ctx.get("active", False):
        return "clarification_questions"  # BYPASS SEARCH
    return "check_cache"  # Normal flow
```

---

## 4. Node Logic: `ClarificationQuestionsNode`

**File:** `app/nodes/clarification_questions/node.py`

This node becomes a **State Controller**. It effectively has two modes of operation based on how it was entered.

### 4.1. Logic Flow (Execute Method)

**Case A: Initialization (Entry from Search Strategy)**
*   **Condition:** `state.get("clarification_task")` is present (set by `HybridSearch` when it detects questions).
*   **Action:**
    1.  Create `ClarificationContext`:
        *   `active = True`
        *   `questions = metadata["clarifying_questions"]`
        *   `current_index = 0`
        *   `answers = {}`
    2.  **Output:** Return the first question (`questions[0]`) to the user.
    3.  **State Update:** `dialog_state` = `NEEDS_CLARIFICATION`.

**Case B: Processing Loop (Entry from Router)**
*   **Condition:** `state["clarification_context"]["active"]` is `True`.
*   **Action:**
    1.  **Capture Answer:** Use `state["last_user_message"]` as the answer to `questions[current_index]`. Store in `answers`.
    2.  **Advance:** `current_index += 1`.
    3.  **Check Status:**
        *   **If `current_index < len(questions)`:**
            *   **Output:** Ask `questions[current_index]`.
            *   Translate question to user's language using a micro-chain (optional but requested).
            *   Keep `active = True`.
            *   Return `dialog_state` = `NEEDS_CLARIFICATION`.
        *   **If `current_index >= len(questions)`:**
            *   **Complete:** Set `active = False`.
            *   **Output:** Empty answer (internal pass-through).
            *   **Route:** Proceed to `PromptRouting` (or `Generation`).
            *   **State Update:** `dialog_state` = `ANSWER_PROVIDED` (or similar).

---

## 5. Final Generation & Handoff

### 5.1. `PromptRoutingNode` (`app/nodes/prompt_routing/node.py`)
This node constructs the inputs for the LLM. It needs to be aware of the collected answers.

*   **Logic:**
    *   Check if `state["clarification_context"]["answers"]` is populated.
    *   **Prompt Construction:**
        ```text
        Context: {original_doc_content}
        
        The user has provided the following details:
        - Question: {q1} -> Answer: {a1}
        - Question: {q2} -> Answer: {a2}
        
        User Query: {original_query}
        ```
    *   This ensures the final answer incorporates the specific details (e.g., "For Android version 12, do this...").

### 5.2. Post-Generation Handoff (`app/nodes/archive_session/node.py` or Router)
The user requires: *Generate Answer -> Then Escalate*.

*   **Mechanism:**
    *   In `StateMachine` or `ArchiveSession`, check:
        `if state["clarification_context"]["requires_handoff"] is True`.
    *   **Action:**
        *   If True, update the `UserSession` status to `escalated` or `human_needed` *after* the generation cycle is complete.
        *   Ensure the UI/Telegram adapter knows to append a "Connecting you to an agent..." footer *after* the AI response.

---

## 6. Implementation Steps Checklist

1.  [ ] **Data Models:** Update `State` (python) and `UserSession` (redis) models.
2.  [ ] **Persistence:** Update `SessionStarter` to read and `ArchiveSession` to write the new context.
3.  [ ] **Routing:** Modify `graph_builder.py` to add the conditional bypass logic.
4.  [ ] **Node Rewrite:** Completely refactor `ClarificationQuestionsNode.execute` to handle the `Init` vs `Loop` logic strictly.
5.  [ ] **Search Integration:** Ensure `HybridSearchNode` correctly populates the initial trigger data (`clarification_task`) but does NOT set `active=True` itself (letting the Clarification node handle init). 
    *   *Correction:* Actually, `HybridSearch` sets the data, and the `StateMachine` routes to `ClarificationQuestions`. That logic remains, but `ClarificationQuestions` handles the setup.
6.  [ ] **Prompting:** Update `PromptRoutingNode` to format the collected Q&A for the `GenerationNode`.
7.  [ ] **Handoff:** Implement the "Generate then Escalate" check in the final stages.

## 7. Example Trace Validation (Future)

**User Input:** "12"
1.  **Start** -> `SessionStarter` loads context (Index=1, Q="Version?").
2.  **Guardrails** -> OK.
3.  **Router** -> Sees `active=True`. Jumps to `ClarificationQuestions`.
4.  **ClarificationNode**:
    *   Recover context: User answering Q[1].
    *   Store "12" for "Version?".
    *   Increment Index -> 2.
    *   Check: Q[2] exists? (Assume "Describe error").
    *   Output: "Can you describe the error?"
5.  **End Turn.**

**Result:** No search performed. "12" captured correctly.
