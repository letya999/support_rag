-- Migration 003: Create conversation management tables

-- 1. Session Archive
-- Stores completed sessions for analytics and history
CREATE TABLE IF NOT EXISTS sessions_archive (
    session_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    duration_seconds FLOAT,
    outcome VARCHAR, -- 'resolved', 'escalated', 'abandoned'
    summary TEXT,
    metrics JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sessions_archive_user_id ON sessions_archive(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_archive_start_time ON sessions_archive(start_time);

-- 2. Session Summaries
-- Stores searchable summaries for RAG context
CREATE TABLE IF NOT EXISTS session_summaries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES sessions_archive(session_id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    search_tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_session_summaries_session_id UNIQUE (session_id)
);

-- 3. User Profiles
-- Long-term memory and user preferences
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR PRIMARY KEY,
    name VARCHAR,
    long_term_memory JSONB DEFAULT '{}'::jsonb, -- structured facts about user
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Escalations
-- Records of handoffs to human agents
CREATE TABLE IF NOT EXISTS escalations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES sessions_archive(session_id) ON DELETE CASCADE,
    reason VARCHAR NOT NULL,
    priority VARCHAR DEFAULT 'normal', -- 'normal', 'high', 'urgent'
    status VARCHAR DEFAULT 'pending', -- 'pending', 'assigned', 'resolved'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_escalations_session_id UNIQUE (session_id)
);
