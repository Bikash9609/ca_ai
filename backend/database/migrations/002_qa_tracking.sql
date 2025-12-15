-- Migration 002: Q&A tracking and page mapping
-- Adds tables for answer grounding, traceability, and page references

-- Q&A tracking for answer grounding
CREATE TABLE IF NOT EXISTS question_answers (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    chunk_ids TEXT NOT NULL,  -- JSON array of chunk IDs used
    model_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES documents(client_id)
);

-- Page mapping for documents
CREATE TABLE IF NOT EXISTS document_pages (
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    start_chunk_index INTEGER,
    end_chunk_index INTEGER,
    text_preview TEXT,
    PRIMARY KEY(document_id, page_number),
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_qa_client_id ON question_answers(client_id);
CREATE INDEX IF NOT EXISTS idx_qa_created_at ON question_answers(created_at);
CREATE INDEX IF NOT EXISTS idx_pages_doc_id ON document_pages(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_page_num ON document_pages(page_number);

-- Entity indexes for fast lookup (using JSON extract)
-- Note: SQLite JSON indexes require FTS5 or manual indexing strategies
-- We'll use metadata JSON field in document_chunks for entity filtering
