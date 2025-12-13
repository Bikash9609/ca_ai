-- CA AI MVP Rules Server Database Schema
-- PostgreSQL 16+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Rules table (for LLM reference)
CREATE TABLE IF NOT EXISTS gst_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(100) UNIQUE NOT NULL,  -- e.g., "itc_36_4"
    name TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    citation TEXT,
    circular_number TEXT,
    effective_from DATE,
    effective_to DATE,
    category VARCHAR(50),  -- "itc", "blocked_credits", "filing"
    version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Rule logic (for deterministic calculations)
CREATE TABLE IF NOT EXISTS gst_rule_logic (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(100) REFERENCES gst_rules(rule_id),
    condition_type VARCHAR(50) NOT NULL,  -- "vendor_not_in_gstr1", etc.
    condition_logic JSONB NOT NULL,
    action_type VARCHAR(50) NOT NULL,  -- "block_itc", "reverse_itc"
    action_percentage DECIMAL(5,2) DEFAULT 100.0,
    action_amount_formula TEXT,
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS gst_rule_embeddings (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES gst_rules(id),
    embedding vector(384),
    chunk_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector index for fast similarity search
CREATE INDEX IF NOT EXISTS gst_rule_embeddings_embedding_idx 
ON gst_rule_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Full-text search index
CREATE INDEX IF NOT EXISTS gst_rules_fts_idx 
ON gst_rules 
USING GIN (to_tsvector('english', rule_text || ' ' || name));

-- Version tracking
CREATE TABLE IF NOT EXISTS gst_rule_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    released_at TIMESTAMP DEFAULT NOW(),
    changelog TEXT,
    rules_count INTEGER
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_gst_rules_category ON gst_rules(category);
CREATE INDEX IF NOT EXISTS idx_gst_rules_version ON gst_rules(version);
CREATE INDEX IF NOT EXISTS idx_gst_rules_active ON gst_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_gst_rule_logic_rule_id ON gst_rule_logic(rule_id);
CREATE INDEX IF NOT EXISTS idx_gst_rule_logic_priority ON gst_rule_logic(priority);

