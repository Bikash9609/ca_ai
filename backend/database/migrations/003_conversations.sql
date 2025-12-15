-- Migration 003: Conversations table for chat history
-- Adds table for managing conversation sessions

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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_conv_client_id ON conversations(client_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at);
CREATE INDEX IF NOT EXISTS idx_msg_conv_id ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_created_at ON conversation_messages(created_at);
