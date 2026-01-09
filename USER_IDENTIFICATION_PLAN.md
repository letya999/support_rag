# User Identification & Fingerprinting System Plan

## 1. Goal
Implement a persistent user identification system that:
1.  **Captures Identity**: Uses Telegram IDs (bot) or Device Fingerprints (API) to recognize users.
2.  **Stores Metadata**: Saves rich context (browser info, telegram username, device specs) in a `metadata` JSONB field for every identity.
3.  **Unifies Identity**: Maps these external identities to a single stable `user_id` (UUID).
4.  **Immediate Persistence**: Records the user content immediately upon the very first interaction.

## 2. Database Schema Changes

### New Table: `user_identities`
Stores the mapping between external identifiers and internal Users, plus rich metadata.

```sql
CREATE TABLE IF NOT EXISTS user_identities (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL, -- The internal stable UUID (links to user_profiles)
    identity_type VARCHAR NOT NULL, -- 'telegram', 'device_fingerprint'
    identity_value VARCHAR NOT NULL, -- The actual tg_id or hash
    metadata JSONB DEFAULT '{}'::jsonb, -- Store raw device info, user agent, telegram user info
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_identity_type_value UNIQUE (identity_type, identity_value)
);

CREATE INDEX idx_identities_user_id ON user_identities(user_id);
```

## 3. Implementation Logic

### Service: `IdentityManager` (`app/services/identity/manager.py`)

**Method**: `get_or_create_user(identity_type: str, identity_value: str, metadata: dict) -> str`

**Workflow**:
1.  **Incoming Request**: System receives `identity_value` (e.g., "tg_12345") and `metadata` (e.g., `{"username": "ivan", "chat_type": "private"}`).
2.  **DB Lookup**:
    *   Query `user_identities` for this type/value.
3.  **Scenario A: User Exists**:
    *   Update `last_seen` timestamp.
    *   Merge new `metadata` with existing (to keep generic info up to date).
    *   **Return**: The existing `user_id`.
4.  **Scenario B: New User**:
    *   Generate new `user_id` (UUID).
    *   Create entry in `user_profiles` (ensures Foreign Key validity).
    *   Create entry in `user_identities` with the passed `metadata`.
    *   **Return**: The new `user_id`.

## 4. Integration Points

### A. Telegram Bot (`POST /rag/query`)
*   **Input**: Request body contains `user_id` (Telegram ID) and extra fields.
*   **Action**:
    1.  Extract `tg_id` from body.
    2.  Extract metadata (construct generic dict from available request fields).
    3.  Call `IdentityManager.get_or_create_user("telegram", tg_id, metadata)`.
    4.  Use resulting UUID for all subsequent logic (Message History, Session creation).

### B. Web API (`GET /ask`, `GET /search`)
*   **Input**: Request headers (e.g., `X-Device-Fingerprint`, `User-Agent`).
*   **Action**:
    1.  Extract fingerprint hash from header (or generate from IP+UA if missing).
    2.  Extract metadata (User-Agent, IP, etc).
    3.  Call `IdentityManager.get_or_create_user("device_fingerprint", hash, metadata)`.
    4.  Use resulting UUID for context.

## 5. Execution Steps

1.  **Migration**: Create `scripts/migrate-006-identity-tables.sql` with the schema above.
2.  **Code**: Implement `IdentityManager` in `app/services/identity/manager.py`.
3.  **Integration**: Modify `app/api/rag_routes.py` and `app/api/rag_routes.py` to use the manager.
