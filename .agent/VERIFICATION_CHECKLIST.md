# Quick Reference: Session History Architecture

## ✅ You Understood Correctly!

### Terminology

**conversation_history** = Messages in CURRENT session
- Where: `messages` table WHERE `session_id = current`
- Loaded by: session_starter (from request OR DB)
- Used for: Generation context in THIS conversation
- Example: Last 20 messages from today's chat

**session_history** = Previous SESSIONS by same user
- Where: `sessions` table + `messages` JOIN, WHERE `user_id = current AND session_id != current`
- Loaded by: session_starter (lazy, on-demand)
- Used for: Long-term context across sessions
- Example: Last 3 conversations user had (yesterday, last week)

---

## Data Flow Guarantee

### session_starter (Load)
```
1. conversation_history:
   - Try: state.get("conversation_history") from request ✅
   - Fallback: Load from messages WHERE session_id = current ✅
   - Deduplicate and limit to 20 messages ✅

2. session_history:
   - Lazy load: sessions + messages JOIN WHERE user_id = X ✅
   - Limit to 3-5 previous sessions ✅
   - Only loaded if prompt_routing needs it ✅
```

### archive_session (Save)
```
For each request:
  1. INSERT INTO sessions (session_id) ON CONFLICT DO NOTHING ✅
     → Creates session record on first message
  
  2. INSERT INTO messages (role='user', content=question) ✅
     → Saves user message
  
  3. INSERT INTO messages (role='assistant', content=answer) ✅
     → Saves bot response
  
  4. UPDATE sessions SET status, end_time ✅
     → Updates session metadata
  
  5. IF escalation: INSERT INTO escalations ✅
     → Tracks handoff
```

---

## Example Scenario

### Timeline: User sends 3 messages

**Message 1:**
- conversation_history from request: [] (empty)
- session_starter loads from DB: [] (new session)
- archive_session writes: 2 rows in `messages`

**Message 2:**
- conversation_history from request: [msg1_user, msg1_bot]
- session_starter: uses request data (no DB query)
- archive_session writes: +2 rows in `messages` (total: 4)

**Message 3:**
- conversation_history from request: [msg1_bot, msg2_user, msg2_bot]
- session_starter: uses request data
- archive_session writes: +2 rows in `messages` (total: 6)

**Result in DB:**
```sql
SELECT * FROM messages WHERE session_id = 'X';
-- 6 rows: 3 user + 3 assistant

SELECT * FROM sessions WHERE session_id = 'X';
-- 1 row: session metadata
```

---

## Files Updated in Plan

### Task 4: Migration
- `scripts/migrate-005-messages-table.sql` ✅
- Creates `messages` and `sessions` tables

### Task 5: archive_session
- `app/nodes/archive_session/node.py` ✅
- Saves each message individually to DB

### Task 6: PersistenceManager
- `app/nodes/persistence/persistence_manager.py` ✅
- `get_session_messages()` - load conversation_history
- `get_user_recent_sessions()` - load session_history

### Task 8: session_starter
- `app/nodes/session_starter/node.py` ✅
- Loads conversation_history from request OR DB
- Lazy loads session_history from DB

---

## Verification

### After implementing, check:

```sql
-- 1. Send 3 messages
-- 2. Verify messages table
SELECT COUNT(*) FROM messages WHERE session_id = 'YOUR_SESSION';
-- Should show: 6 (3 user + 3 assistant)

-- 3. Verify session metadata
SELECT * FROM sessions WHERE session_id = 'YOUR_SESSION';
-- Should show: 1 row with status='active'

-- 4. Check conversation_history loaded
-- Look at Langfuse trace for session_starter output
-- Should show: conversation_history with all messages
```

---

## ✅ Guarantees

1. **session_starter WILL load:**
   - conversation_history from request (fast path)
   - OR from messages table (fallback)
   - Deduplicates and filters noise

2. **archive_session WILL save:**
   - Each user message to messages table
   - Each assistant response to messages table
   - Session metadata to sessions table
   - Escalations to escalations table (if triggered)

3. **No data loss:**
   - Every message persisted in DB
   - Session metadata tracked separately
   - History available for future sessions

**Plan fully supports your understanding! ✅**
