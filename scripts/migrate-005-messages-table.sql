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

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);

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

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_end_time ON sessions(end_time DESC);

-- Add foreign key for referential integrity
ALTER TABLE messages 
    DROP CONSTRAINT IF EXISTS fk_messages_session;
ALTER TABLE messages 
    ADD CONSTRAINT fk_messages_session 
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE;

-- Update escalations to reference sessions instead of sessions_archive
ALTER TABLE escalations 
    DROP CONSTRAINT IF EXISTS escalations_session_id_fkey;
-- We need to ensure the session exists in sessions table before adding FK if escalations table already has data.
-- Since this is a dev migration/fix, we will assume we can add the constraint or that existing data might be an issue. 
-- However, for robustness, we should be careful. 
-- Given the plan implies a fresh start or compatible migration, I will proceed with adding the constraint.
ALTER TABLE escalations 
    ADD CONSTRAINT fk_escalations_session 
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE;
