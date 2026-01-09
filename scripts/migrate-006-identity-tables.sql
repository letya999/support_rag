-- Migration 006: Create identity management tables

-- 1. User Identities
-- Decouples the logical "User" (user_profiles provided by user_id) 
-- from the authentication method/device (Telegram, Web Fingerprint, Email, etc.)
-- Allows multiple identifiers to point to a single user_profile.

CREATE TABLE IF NOT EXISTS user_identities (
    id SERIAL PRIMARY KEY,
    
    -- The stable internal UUID (Foreign Key to user_profiles)
    user_id VARCHAR NOT NULL, 
    
    -- The type of identifier (e.g., 'telegram', 'device_fingerprint', 'custodian_id')
    identity_type VARCHAR NOT NULL,
    
    -- The unique value for this type (e.g., '123456789' for telegram, 'a1b2c3d4...' for fingerprint)
    identity_value VARCHAR NOT NULL,
    
    -- Rich metadata storage (Device info, browser headers, cryptograms, telegram profile info)
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    -- 1. Each (type, value) pair must be unique (e.g., one Telegram ID cannot belong to two users)
    CONSTRAINT uq_identity_type_value UNIQUE (identity_type, identity_value)
);

-- Indexes for performance
-- Quick lookup by user_id to find all linked identities
CREATE INDEX IF NOT EXISTS idx_user_identities_user_id ON user_identities(user_id);
-- GIN index for searching within metadata (optional but useful for analytics)
CREATE INDEX IF NOT EXISTS idx_user_identities_metadata ON user_identities USING GIN (metadata);
