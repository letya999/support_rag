# Architecture Summary: Client-Agnostic RAG Pipeline

## ✅ Corrected Architecture

### Core Principle: SEPARATION OF CONCERNS

```
┌─────────────┐
│   Client    │ (Telegram/Web/API)
│  (Any)      │ → Sends: user_id, session_id, question
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│          RAG Pipeline Nodes                  │
│  (Client-Agnostic - No Telegram Dependencies)│
└──────┬──────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│      PersistenceManager                      │
│  (Service Layer - Knows DB Schema)           │
└──────┬──────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│           Database                           │
│  (messages, sessions, escalations)           │
└──────────────────────────────────────────────┘
```

---

## Node Responsibilities

### session_starter (LOAD)
**What it does:**
- Receives: `user_id`, `session_id` from state
- Loads conversation_history from DB via PersistenceManager
- Filters system noise
- Returns: clean conversation_history

**What it DOESN'T do:**
- ❌ Check request payload
  - ❌ Parse telegram messages
- ❌ Know about DB schema
- ❌ Direct SQL queries

**Code:**
```python
# ✅ CORRECT
raw_history = await PersistenceManager.get_session_messages(session_id)
updates["conversation_history"] = filter_conversation_history(raw_history)

# ❌ WRONG
raw_history = state.get("conversation_history")  # Don't depend on client!
```

---

### archive_session (SAVE)
**What it does:**
- Receives: question, answer from state
- Saves via PersistenceManager.save_message()
- Updates session metadata via PersistenceManager.update_session()
- Saves escalations if needed

**What it DOESN'T do:**
- ❌ Direct SQL queries
- ❌ Know about messages/sessions tables
- ❌ Depend on client format

**Code:**
```python
# ✅ CORRECT
await PersistenceManager.save_message(
    session_id=session_id,
    user_id=user_id,
    role="user",
    content=question
)

# ❌ WRONG
await cur.execute("INSERT INTO messages...")  # Don't write SQL in nodes!
```

---

### PersistenceManager (SERVICE LAYER)
**What it does:**
- ALL database access
- Knows SQL and schema
- Provides clean interface for nodes

**Methods:**
- `save_message()` - write user/assistant message
- `update_session()` - update session metadata
- `get_session_messages()` - load conversation_history
- `get_user_recent_sessions()` - load session_history
- `save_escalation()` - record handoff event

**Benefits:**
- ✅ Single source of truth for DB access
- ✅ Easy to change DB (just update this class)
- ✅ Easy to mock for testing
- ✅ Nodes stay clean and focused

---

## Data Flow Example

### Incoming Request
```
Client → API Handler → Pipeline
{
  "user_id": "480637186",
  "session_id": "480637186_1767475520",
  "question": "Как доставить быстрее?"
}
```

### session_starter Execution
```python
# 1. Load from DB (NOT from request)
messages = await PersistenceManager.get_session_messages(
    session_id="480637186_1767475520",
    limit=20
)
# Returns: [
#   {role: 'user', content: 'Вопрос 1'},
#   {role: 'assistant', content: 'Ответ 1'},
#   ...
# ]

# 2. Filter and return
conversation_history = filter_conversation_history(messages)
return {"conversation_history": conversation_history}
```

### archive_session Execution
```python
# 1. Save user message
await PersistenceManager.save_message(
    session_id="480637186_1767475520",
    user_id="480637186",
    role="user",
    content="Как доставить быстрее?"
)

# 2. Save bot response
await PersistenceManager.save_message(
    session_id="480637186_1767475520",
    user_id="480637186",
    role="assistant",
    content="Можно выбрать экспресс-доставку...",
    metadata={"confidence": 0.95}
)

# 3. Update session
await PersistenceManager.update_session(
    session_id="480637186_1767475520",
    user_id="480637186",
    channel="telegram",
    status="active"
)
```

---

## Benefits of This Architecture

### 1. Client Agnostic
- ✅ Works with Telegram, Web, API equally
- ✅ No special handling per client
- ✅ Easy to add new channels (WhatsApp, Slack)

### 2. Testability
- ✅ Mock PersistenceManager for unit tests
- ✅ No DB needed for node tests
- ✅ Integration tests only at service layer

### 3. Maintainability
- ✅ Change DB schema → update only PersistenceManager
- ✅ Change storage backend → update only PersistenceManager
- ✅ Nodes stay clean and focused

### 4. Single Source of Truth
- ✅ DB is the only history source
- ✅ No inconsistency between client and server
- ✅ Reliable conversation state

---

## What Changed

### BEFORE (❌ WRONG)
```python
# session_starter depended on request
raw_history = state.get("conversation_history", [])  # From telegram
if not raw_history:
    # Load from DB as fallback
    raw_history = await load_from_db()
```

### AFTER (✅ CORRECT)
```python
# session_starter ALWAYS loads from DB
raw_history = await PersistenceManager.get_session_messages(session_id)
# Client-agnostic, single source of truth
```

---

### BEFORE (❌ WRONG)
```python
# archive_session wrote SQL directly
async with conn.cursor() as cur:
    await cur.execute("INSERT INTO messages...")
```

### AFTER (✅ CORRECT)
```python
# archive_session uses service layer
await PersistenceManager.save_message(...)
# No SQL in nodes
```

---

## Implementation Summary

**Files Updated:**
1. `session_starter/node.py` - Always load from DB
2. `archive_session/node.py` - Use PersistenceManager
3. `persistence/persistence_manager.py` - Add service methods
4. `scripts/migrate-005-messages-table.sql` - New schema

**Key Principles Applied:**
- ❌ Nodes don't know about clients (telegram/web)
- ❌ Nodes don't write SQL
- ✅ Nodes use PersistenceManager
- ✅ DB is single source of truth
