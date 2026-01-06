# Session & History Appendix

## Terminology Clarification

**session_id** = Unique identifier for a conversation session
- Provided by client (telegram bot creates session_id per chat)
- Format: `{user_id}_{timestamp}` (e.g., "480637186_1767475520")

**conversation_history** = Messages within CURRENT session
- Source: `state.get("conversation_history")` from request + DB if needed
- Used for: Generation context, dialog analysis
- Limit: Last N messages (e.g., 20) from current session_id

**session_history** = Previous sessions by same user
- Source: `sessions` table WHERE user_id = X AND session_id != current
- Used for: Long-term user context ("what did we discuss before")
- Limit: Last M sessions (e.g., 3-5)

---

## session_starter Implementation

**What it does:**
1. Receives `conversation_history` from request (telegram bot sends last N messages)
2. Optionally loads MORE messages from DB if conversation_history is incomplete
3. Loads session_history (previous sessions) for user context
4. Filters system noise

**Updated execute() method:**

```python
async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
    """Load conversation and session history."""
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    
    if not user_id:
        return {}
    
    updates = {}
    
    # 1. Filter conversation_history from request
    raw_history = state.get("conversation_history", [])
    if raw_history:
        clean_history = filter_conversation_history(raw_history)
        if len(clean_history) != len(raw_history):
            updates["conversation_history"] = clean_history
    
    # 2. Load additional messages from DB if needed
    if not raw_history or len(raw_history) < 5:
        try:
            from app.nodes.persistence import PersistenceManager
            db_messages = await PersistenceManager.get_session_messages(
                session_id=session_id,
                limit=20  # Last 20 messages from this session
            )
            # Merge with existing history
            updates["conversation_history"] = db_messages + (raw_history or [])
        except Exception as e:
            print(f"⚠️ Failed to load conversation history from DB: {e}")
    
    # 3. Lazy load session_history (previous sessions)
    updates["_session_history_loader"] = lambda: PersistenceManager.get_user_recent_sessions(
        user_id=user_id,
        limit=3  # Last 3 sessions (excluding current)
    )
    
    # 4. Load user profile
    if self.params.get("load_user_profile", True):
        try:
            updates["user_profile"] = await self._load_user_profile(user_id)
        except Exception as e:
            print(f"⚠️ Error loading profile: {e}")
    
    # 5. Manage Redis session state
    active_session = await self._ensure_redis_session(user_id, session_id)
    if active_session:
        updates["attempt_count"] = active_session.attempt_count
        if active_session.extracted_entities:
            updates["extracted_entities"] = active_session.extracted_entities
    
    return updates
```

**Key Points:**
- ✅ conversation_history = current session messages (from request OR DB)
- ✅ session_history = previous sessions (lazy loaded)
- ✅ No confusion: each serves different purpose

---

## Example Data Flow

### Scenario: User sends 3 messages in one session

**Step 1:** First message
```
conversation_history (from request): []  -- Empty on first message
session_starter: Loads from DB, finds nothing (new session)
archive_session: 
  - INSERT sessions (session_id='user_123')
  - INSERT messages (role='user', content='Вопрос 1')
  - INSERT messages (role='assistant', content='Ответ 1')
```

**Step 2:** Second message (same session)
```
conversation_history (from request): [
  {role: 'assistant', content: 'Ответ 1'},
  {role: 'user', content: 'Вопрос 2'}
]
session_starter: Uses request history (already has context)
archive_session:
  - sessions already exists (ON CONFLICT DO NOTHING)
  - INSERT messages (role='user', content='Вопрос 2')
  - INSERT messages (role='assistant', content='Ответ 2')
```

**Database State After 3 Messages:**

```sql
-- messages table: 6 rows
SELECT * FROM messages WHERE session_id = 'user_123';
| id | session_id | role      | content   | created_at |
|----|-----------|-----------|-----------|------------|
| 1  | user_123  | user      | Вопрос 1  | 20:00:00   |
| 2  | user_123  | assistant | Ответ 1   | 20:00:05   |
| 3  | user_123  | user      | Вопрос 2  | 20:01:00   |
| 4  | user_123  | assistant | Ответ 2   | 20:01:05   |
| 5  | user_123  | user      | Вопрос 3  | 20:02:00   |
| 6  | user_123  | assistant | Ответ 3   | 20:02:05   |

-- sessions table: 1 row
SELECT * FROM sessions WHERE session_id = 'user_123';
| session_id | user_id | status | start_time | end_time |
|-----------|---------|--------|------------|----------|
| user_123  | 123     | active | 20:00:00   | 20:02:05 |
```

---

## Verification Queries

### Check conversation_history (current session)
```sql
-- What session_starter would load
SELECT role, content, created_at 
FROM messages 
WHERE session_id = 'CURRENT_SESSION_ID'
ORDER BY created_at ASC
LIMIT 20;
```

### Check session_history (previous sessions)
```sql
-- What prompt_routing would use for context
SELECT s.session_id, s.status, s.start_time, COUNT(m.id) as msg_count
FROM sessions s
LEFT JOIN messages m ON s.session_id = m.session_id
WHERE s.user_id = 'USER_ID' 
  AND s.session_id != 'CURRENT_SESSION_ID'
  AND s.status != 'active'
GROUP BY s.session_id
ORDER BY s.end_time DESC
LIMIT 3;
```
