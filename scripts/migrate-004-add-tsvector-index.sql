-- Migration to add optimized tsvector column for combined search
-- Adapting from PIPELINE_OPTIMIZATION_ROADMAP.md for actual 'documents' table structure

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS search_vector tsvector 
GENERATED ALWAYS AS (
    setweight(to_tsvector('russian', coalesce(content, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'B')
) STORED;

-- Create GIN index
CREATE INDEX IF NOT EXISTS idx_documents_search_vector ON documents USING GIN(search_vector);

-- Create index on category in metadata
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents((metadata->>'category'));

-- Analyze for planner
ANALYZE documents;
