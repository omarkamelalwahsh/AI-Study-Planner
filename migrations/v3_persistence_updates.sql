-- Migration to add persistence fields for ChatSession state and indexes
-- Up Migration
ALTER TABLE chat_sessions
ADD COLUMN IF NOT EXISTS state JSONB NOT NULL DEFAULT '{}'::jsonb;
-- Ensure cascade delete is set (if not already handled by schema creation, strictly enforcing here might require dropping constraint)
-- For existing tables, we assume the FK exists. If we want to ensure ON DELETE CASCADE:
ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_session_id_fkey;
ALTER TABLE chat_messages
ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;
-- Add composite index for performance on history loading
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages(session_id, created_at);