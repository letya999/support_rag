# RAG Pipeline Fixes: Implementation Plan

## Executive Summary

**Objective:** Fix conversation history flow, database persistence, and prompt routing in the RAG pipeline.

**Core Issues:**
1. ❌ Generation node doesn't receive conversation history
2. ❌ Escalations not persisted to database
3. ❌ sessions_archive overwrites instead of accumulating
4. ⚠️ Unclear session_summaries vs sessions_archive purpose

---

## Database Schema Redesign

### ❌ Current Schema Problems

**sessions_archive** stores entire conversation as TEXT summary → Can't query individual messages  
**session_summaries** duplicates session_archive data → Confusing and redundant  
**Both tables** use UNIQUE constraints → Can't track conversation evolution

### ✅ Proposed Schema (Industry Standard)

#### 1. `messages` (Core Table)
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,              -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'         -- confidence, intent, etc.
);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_messages_user ON messages(user_id, created_at);
```

**Purpose:** Store every message individually  
**Benefits:** 
- Granular analytics (response time per message)
- Easy conversation history loading
- Simple to add features (reactions, edits)

#### 2. `sessions` (Lightweight Metadata)
```sql
CREATE TABLE sessions (
    session_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    channel VARCHAR,                    -- 'telegram' | 'web' | 'whatsapp'
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status VARCHAR DEFAULT 'active',    -- 'active' | 'resolved' | 'escalated'
    metadata JSONB DEFAULT '{}'         -- avg_confidence, total_messages, etc.
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
```

**Purpose:** Session-level metadata only  
**NO DUPLICATION:** Content lives in `messages`, not here

#### 3. `escalations` (Unchanged)
```sql
-- Keep as is, works fine
```

### Migration Strategy

**Option A: Fresh Start (Development)**
- Drop `sessions_archive`, `session_summaries`
- Create `messages`, `sessions`
- Update archive_session to save individual messages

**Option B: Gradual Migration (Production)**
- Create new tables alongside old ones
- Archive to both schemas during transition
- Switch reads to new schema when ready
- Drop old tables after verification

---

## Architecture Decisions

### ✅ Conversation History Flow

```
Request (from any client: telegram/web/API)
  → user_id, session_id, question
  → session_starter: LOADS conversation_history from DB (via PersistenceManager)
  → dialog_analysis: analyzes for signals (uses loaded history)
  → aggregation: extracts entities from CURRENT question only (NO history)
  → retrieval: searches docs using entities
  → prompt_routing: builds system_prompt with history + profile
  → generation: receives complete system_prompt, generates answer
  → archive_session: SAVES messages to DB (via PersistenceManager)
```

**Key Principles:**
1. History used for GENERATION, NOT for RETRIEVAL
2. Nodes are CLIENT-AGNOSTIC (no telegram/web dependencies)
3. ALL DB access through PersistenceManager (service layer)

### ✅ Database Persistence Strategy

**sessions_archive:**
- Each message → UPDATE existing record (accumulate summary)
- New session → INSERT new record
- Distinguish by: check if session_id exists

**session_summaries:**
- Every N messages (e.g., 5) → INSERT new chunk
- Remove UNIQUE constraint, add chunk_number
- Enables incremental summarization

**escalations:**
- On first escalation → INSERT
- Keep UNIQUE constraint (one escalation per session max)

---

## Implementation Tasks

### Task 1: Fix Conversation History in dialog_analysis

**File:** `app/nodes/dialog_analysis/node.py`

**Current Code (line 35):**
```python
history = state.get("conversation_history") or state.get("session_history", []) or []
```

**Issue:** Works correctly, but conversation_history might be empty on first message after escalation (this is normal).

**Action:** ✅ NO CHANGE NEEDED. Add debug logging to verify history arrives:

```python
history = state.get("conversation_history") or state.get("session_history", []) or []
print(f"🔍 dialog_analysis: Got {len(history)} history messages")
```

**File:** `app/nodes/dialog_analysis/llm.py`

**Same change at line 24.**

---

### Task 2: Prompt Routing → Generation Pipeline

**Current Issue:** `generation/node.py` recreates human prompt, losing history from system_prompt.

**Solution:** prompt_routing should prepare BOTH system and human prompts.

**File:** `app/nodes/prompt_routing/node.py`

**Add after line 214:**
```python
# Build human prompt with docs
human_prompt = f"Context:\n{docs_str}\n\nQuestion: {question}"

return {
    "system_prompt": system_prompt,
    "human_prompt": human_prompt,  # NEW
    "prompt_hint": state_behavior.get("prompt_hint", "standard")
}
```

**File:** `app/nodes/generation/node.py`

**Replace execute() method:**
```python
async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
    # Use pre-built prompts from prompt_routing
    system_prompt = state.get("system_prompt")
    human_prompt = state.get("human_prompt")
    
    if not human_prompt:
        # Fallback: build from docs + question
        question = state.get("aggregated_query") or state.get("question")
        docs = state.get("docs", [])
        docs_str = "\n\n".join(docs)
        human_prompt = f"Context:\n{docs_str}\n\nQuestion: {question}"
    
    # Build chain
    if system_prompt:
        escaped = system_prompt.replace("{", "{{").replace("}", "}}")
        chain = ChatPromptTemplate.from_messages([
            ("system", escaped),
            ("human", "{human_prompt}")
        ]) | get_llm()
    else:
        chain = self.qa_prompt | get_llm()
    
    response = await chain.ainvoke({"human_prompt": human_prompt})
    return {"answer": response.content}
```

---

### Task 3: Escalations to Database ✅ DONE

**File:** `app/nodes/persistence/persistence_manager.py`

**Add method:**
```python
@staticmethod
async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
    """Record escalation event."""
    from app.storage.connection import get_db_connection
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO escalations (session_id, reason, priority, status, created_at)
                VALUES (%s, %s, %s, 'pending', NOW())
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, reason, priority)
            )
```

**File:** `app/nodes/archive_session/node.py`

**Add after line 111 (after profile update):**
```python
# 1.5. Save Escalation if triggered
if state.get("escalation_triggered"):
    try:
        priority = "high" if state.get("safety_violation") else "normal"
        await PersistenceManager.save_escalation(
            session_id=session_id,
            reason=state.get("escalation_reason", "unknown"),
            priority=priority
        )
    except Exception as e:
        print(f"⚠️ Error saving escalation: {e}")
```

---

### Task 4: Create New Database Schema ✅ DONE

**File:** `scripts/migrate-005-messages-table.sql`

```sql
-- New schema for proper message storage
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_messages_user ON messages(user_id, created_at DESC);
CREATE INDEX idx_messages_created ON messages(created_at DESC);

-- Lightweight sessions metadata
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    channel VARCHAR DEFAULT 'telegram',
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status VARCHAR DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'escalated', 'abandoned')),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_end_time ON sessions(end_time DESC);

-- Add foreign key for referential integrity
ALTER TABLE messages 
    ADD CONSTRAINT fk_messages_session 
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE;

-- Update escalations to reference sessions instead of sessions_archive
ALTER TABLE escalations 
    DROP CONSTRAINT IF EXISTS escalations_session_id_fkey;
ALTER TABLE escalations 
    ADD CONSTRAINT fk_escalations_session 
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE;
```

**Run migration:**
```bash
docker exec -i postgres psql -U user -d ragdb < scripts/migrate-005-messages-table.sql
```

---

### Task 5: Update Archive Session Logic ✅ DONE

**File:** `app/nodes/archive_session/node.py`

**Goal:** Save messages through PersistenceManager (service layer).

**Architecture:**
- ❌ NO direct SQL queries in node
- ✅ ALL DB access through PersistenceManager
- ✅ Node only orchestrates, service handles persistence

**Replace entire execute() method:**

```python
async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
    """Save message and update session metadata."""
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    question = state.get("question", "")
    answer = state.get("answer", "")
    
    if not user_id or not session_id:
        return {}
    
    from app.nodes.persistence import PersistenceManager
    
    try:
        # 1. Save user message
        if question:
            await PersistenceManager.save_message(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=question,
                metadata={
                    "detected_language": state.get("detected_language"),
                    "sentiment": state.get("sentiment")
                }
            )
        
        # 2. Save assistant response (filter system messages)
        if answer and not _is_system_message(answer):
            await PersistenceManager.save_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=answer,
                metadata={
                    "confidence": state.get("confidence"),
                    "matched_intent": state.get("matched_intent"),
                    "docs_count": len(state.get("docs", []))
                }
            )
        
        # 3. Update session metadata
        status = "escalated" if state.get("escalation_triggered") else "active"
        await PersistenceManager.update_session(
            session_id=session_id,
            user_id=user_id,
            channel="telegram",  # TODO: get from state or config
            status=status,
            metadata={
                "last_confidence": state.get("confidence", 0),
                "attempt_count": state.get("attempt_count", 0)
            }
        )
        
        # 4. Save escalation if triggered
        if state.get("escalation_triggered"):
            priority = "high" if state.get("safety_violation") else "normal"
            await PersistenceManager.save_escalation(
                session_id=session_id,
                reason=state.get("escalation_reason", "unknown"),
                priority=priority
            )
        
        # 5. Update user profile
        if state.get("extracted_entities"):
            await PersistenceManager.save_user_profile_update(
                user_id=user_id,
                profile_update=state.get("extracted_entities")
            )
        
    except Exception as e:
        print(f"⚠️ Error archiving session: {e}")
        return {"session_archived": False, "error": str(e)}
    
    # 6. Update Redis session state (optional cache layer)
    try:
        from app.cache.cache_layer import get_cache_manager
        from app.cache.session_manager import SessionManager
        
        cache_manager = await get_cache_manager()
        if cache_manager.redis_client:
            session_manager = SessionManager(cache_manager.redis_client)
            await session_manager.update_state(session_id, {
                "dialog_state": state.get("dialog_state"),
                "attempt_count": state.get("attempt_count", 0)
            })
    except Exception as e:
        print(f"⚠️ Redis update failed (non-critical): {e}")
    
    return {"session_archived": True}
```

**Key Changes:**
1. ✅ **No direct SQL** - uses PersistenceManager.save_message()
2. ✅ **Service layer** - PersistenceManager knows about DB schema
3. ✅ **Separation of concerns** - node orchestrates, service persists
4. ✅ **Easy to test** - mock PersistenceManager

**Benefits:**
- Node doesn't know about messages/sessions tables
- Easy to change DB schema (only update PersistenceManager)
- Can switch to different storage (MongoDB, etc.) without changing nodes
- Cleaner error handling

---

### Task 6: Update PersistenceManager (Service Layer)

**File:** `app/nodes/persistence/persistence_manager.py`

**Goal:** Add methods that nodes need for DB access.

**Add these methods:**

```python
@staticmethod
async def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    metadata: dict = None
):
    """Save a single message to DB."""
    from app.storage.connection import get_db_connection
    import json
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO messages (session_id, user_id, role, content, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, user_id, role, content, json.dumps(metadata or {}))
            )

@staticmethod
async def update_session(
    session_id: str,
    user_id: str,
    channel: str,
    status: str,
    metadata: dict = None
):
    """Create or update session metadata."""
    from app.storage.connection import get_db_connection
    import json
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Create session if doesn't exist
            await cur.execute(
                """
                INSERT INTO sessions (session_id, user_id, channel, status)
                VALUES (%s, %s, %s, 'active')
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, user_id, channel)
            )
            
            # Update status and metadata
            await cur.execute(
                """
                UPDATE sessions SET
                    status = %s,
                    end_time = NOW(),
                    metadata = %s::jsonb
                WHERE session_id = %s
                """,
                (status, json.dumps(metadata or {}), session_id)
            )

@staticmethod
async def get_session_messages(
    session_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Load message history for a session."""
    from app.storage.connection import get_db_connection
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT role, content, created_at, metadata
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (session_id, limit)
            )
            rows = await cur.fetchall()
            
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "metadata": row[3] or {}
                }
                for row in rows
            ]

@staticmethod
async def get_user_recent_sessions(
    user_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Load recent sessions for a user (for context)."""
    from app.storage.connection import get_db_connection
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT s.session_id, s.start_time, s.status, s.metadata,
                       COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON s.session_id = m.session_id
                WHERE s.user_id = %s AND s.status != 'active'
                GROUP BY s.session_id, s.start_time, s.status, s.metadata
                ORDER BY s.end_time DESC NULLS LAST
                LIMIT %s
                """,
                (user_id, limit)
            )
            rows = await cur.fetchall()
            
            return [
                {
                    "session_id": row[0],
                    "start_time": row[1].isoformat() if row[1] else None,
                    "status": row[2],
                    "metadata": row[3] or {},
                    "message_count": row[4]
                }
                for row in rows
            ]

@staticmethod
async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
    """Record escalation event."""
    from app.storage.connection import get_db_connection
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO escalations (session_id, reason, priority, status)
                VALUES (%s, %s, %s, 'pending')
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, reason, priority)
            )
```

**Key Points:**
- ✅ Centralized DB access - all SQL in one place
- ✅ Type hints for clarity
- ✅ Error handling at service layer
- ✅ Nodes don't need to know SQL

---

### Task 7: Aggregation - No History in Retrieval

**File:** `app/nodes/aggregation/node.py`

**Verify current behavior:**
- `lightweight` mode: extracts entities from CURRENT question only ✅
- `llm` mode: uses conversation_history for rewriting ⚠️

**Change:** Force lightweight mode by default, use LLM only when explicitly configured.

**In config:** `app/nodes/aggregation/config.yaml`
```yaml
mode: lightweight  # NOT llm
```

**No code changes needed if config is correct.**

---

### Task 8: Update session_starter for New Schema

**File:** `app/nodes/session_starter/node.py`

**Goal:** Load conversation_history ALWAYS from DB (client-agnostic).

**Architecture:**
- ❌ NO dependency on request payload (telegram-specific)
- ✅ ALWAYS load from PersistenceManager (service layer)
- ✅ Filter system noise after loading

**Replace execute() method:**

```python
async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
    """Load conversation and session history from DB."""
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    
    if not user_id or not session_id:
        return {}
    
    updates = {}
    
    # 1. Load conversation_history from DB (current session)
    try:
        from app.nodes.persistence import PersistenceManager
        raw_history = await PersistenceManager.get_session_messages(
            session_id=session_id,
            limit=20  # Last 20 messages from this session
        )
        
        # Filter system noise
        if raw_history:
            from app.nodes._shared_config.history_filter import filter_conversation_history
            clean_history = filter_conversation_history(raw_history)
            updates["conversation_history"] = clean_history
            print(f"✅ session_starter: Loaded {len(clean_history)} messages from DB")
        else:
            updates["conversation_history"] = []
            print(f"ℹ️ session_starter: No messages found (new session)")
    except Exception as e:
        print(f"⚠️ Failed to load conversation history from DB: {e}")
        updates["conversation_history"] = []
    
    # 2. Lazy load session_history (previous sessions)
    updates["_session_history_loader"] = lambda: PersistenceManager.get_user_recent_sessions(
        user_id=user_id,
        limit=3  # Last 3 completed sessions (excluding current)
    )
    
    # 3. Load user profile
    if self.params.get("load_user_profile", True):
        try:
            updates["user_profile"] = await self._load_user_profile(user_id)
        except Exception as e:
            print(f"⚠️ Error loading profile: {e}")
    
    # 4. Manage Redis session state
    active_session = await self._ensure_redis_session(user_id, session_id)
    if active_session:
        updates["attempt_count"] = active_session.attempt_count
        if active_session.extracted_entities:
            updates["extracted_entities"] = active_session.extracted_entities
    
    return updates
```

**Key Changes:**
1. ✅ **Removed** request dependency - no `state.get("conversation_history")`
2. ✅ **Always** loads from DB via PersistenceManager
3. ✅ **Client-agnostic** - works with telegram/web/API equally
4. ✅ **Single source of truth** - DB is the only history source

**Benefits:**
- Works with ANY client (telegram, web, API)
- No special handling needed in telegram bot
- Consistent behavior across all channels
- Easier testing (mock PersistenceManager)

---

## Testing Checklist

### Verify Database Schema
```sql
-- Check tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check messages table structure
\d messages

-- Check sessions table structure
\d sessions
```

### Verify Message Storage
```sql
-- 1. Send 3 messages
-- 2. Check messages table
SELECT session_id, role, LEFT(content, 50), created_at 
FROM messages 
ORDER BY created_at DESC 
LIMIT 10;

-- Should show: 3 user messages + 3 assistant messages = 6 rows

-- 3. Check session metadata
SELECT session_id, status, start_time, end_time, metadata
FROM sessions
WHERE session_id = 'YOUR_SESSION_ID';

-- Should show: 1 session with status='active'
```

### Verify Escalation Flow
```sql
-- 1. Send toxic message (triggers safety_violation)
-- 2. Check escalations table
SELECT session_id, reason, priority, status, created_at
FROM escalations
WHERE session_id = 'YOUR_SESSION_ID';

-- Should show: 1 escalation with priority='high'

-- 3. Check session status
SELECT status FROM sessions WHERE session_id = 'YOUR_SESSION_ID';

-- Should show: status='escalated'
```

### Verify History in Generation
1. Send first message: "Доставляете в Казахстан?"
2. Send follow-up: "За неделю в Алматы доставите?"
3. Check Langfuse trace:
   - `generation` input should contain system_prompt
   - system_prompt should contain "ASSISTANT: Да, мы осуществляем..."
4. Response should reference Kazakhstan

### Performance Check
```sql
-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM messages WHERE session_id = 'test_session' ORDER BY created_at;

-- Should use idx_messages_session
```

---

## Success Criteria

✅ **Database:**
- `messages` table stores individual user/assistant messages
- `sessions` table tracks session metadata (status, timestamps)  
- `escalations` table populated when handoff occurs
- Each Q&A creates 2 rows in `messages` (user + assistant)

✅ **History Flow:**
- Generation receives conversation history in system_prompt
- dialog_analysis logs show history count > 0 on follow-up
- Follow-up questions reference previous context

✅ **Performance:**
- Session history loaded in <100ms (indexed queries)
- No summary accumulation issues
- Simple SELECT queries for analytics

✅ **Maintainability:**
- Clear schema: messages separate from metadata
- Easy to add features (reactions, edits, attachments)
- Standard chat application pattern

