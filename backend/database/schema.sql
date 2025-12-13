-- CA AI MVP Client Database Schema
-- SQLite with FTS5 and sqlite-vec support

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    period TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    category TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT UNIQUE,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'indexed',
    metadata JSON
);

-- Document chunks (for vector search)
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB,  -- Vector embedding
    metadata JSON,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
    text,
    metadata UNINDEXED,
    content=document_chunks,
    content_rowid=rowid
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_doc_period ON documents(period, category);
CREATE INDEX IF NOT EXISTS idx_chunk_doc_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_client_id ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);
