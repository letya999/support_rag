-- Add full-text search support
-- We create a generated column for performance, but you can also search dynamically.
-- Using 'english' as the default language for now.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_en tsvector 
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_documents_fts_en ON documents USING GIN (fts_en);

-- Also add Russian support just in case, as the prompt was in Russian
ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_ru tsvector 
GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_documents_fts_ru ON documents USING GIN (fts_ru);
