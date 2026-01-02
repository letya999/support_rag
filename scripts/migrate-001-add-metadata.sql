-- Migration: Add metadata column to documents table
-- 'metadata' column will store flexible JSON data including category, intent, etc.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create a GIN index on the metadata column for efficient querying of JSON fields
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin (metadata);
