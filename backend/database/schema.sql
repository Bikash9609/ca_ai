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

-- Additional indexes for Q&A and pages
CREATE INDEX IF NOT EXISTS idx_qa_client_id ON question_answers(client_id);
CREATE INDEX IF NOT EXISTS idx_qa_created_at ON question_answers(created_at);
CREATE INDEX IF NOT EXISTS idx_pages_doc_id ON document_pages(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_page_num ON document_pages(page_number);

-- Conversations table for chat history
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    title TEXT,
    provider TEXT DEFAULT 'claude',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    tool_calls TEXT,  -- JSON array of tool calls
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Indexes for conversations
CREATE INDEX IF NOT EXISTS idx_conv_client_id ON conversations(client_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at);
CREATE INDEX IF NOT EXISTS idx_msg_conv_id ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_created_at ON conversation_messages(created_at);
