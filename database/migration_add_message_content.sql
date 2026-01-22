-- Database migration for Career Copilot RAG
-- This migration adds role and content columns to chat_messages table
-- for storing actual message content.
--
-- Run this SQL against your PostgreSQL database before using the updated API.
-- NOTE: If the table is empty, you can drop and recreate. Otherwise, use ALTER TABLE.
-- Option 1: ALTER TABLE (safe for existing data)
-- Run these if the chat_messages table already exists with data:
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS role VARCHAR(20);
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS content TEXT;
-- Make them non-nullable if table is empty or after backfilling:
-- ALTER TABLE chat_messages ALTER COLUMN role SET NOT NULL;
-- ALTER TABLE chat_messages ALTER COLUMN content SET NOT NULL;
-- Option 2: If table is empty or can be recreated
-- (Uncomment and use if you want to recreate the table)
/*
 DROP TABLE IF EXISTS chat_messages;
 
 CREATE TABLE chat_messages (
 id SERIAL PRIMARY KEY,
 session_id UUID REFERENCES chat_sessions(id),
 request_id UUID DEFAULT gen_random_uuid(),
 role VARCHAR(20) NOT NULL,
 content TEXT NOT NULL,
 user_message_hash VARCHAR(64),
 intent VARCHAR(50),
 retrieved_course_count INTEGER,
 response_length INTEGER,
 latency_ms INTEGER,
 error_occurred BOOLEAN DEFAULT FALSE,
 error_type VARCHAR(100),
 created_at TIMESTAMP DEFAULT NOW()
 );
 
 CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
 CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);
 */
-- Verify the migration
SELECT column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_messages'
ORDER BY ordinal_position;