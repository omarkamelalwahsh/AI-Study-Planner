-- SQL Migration to enable CASCADE delete on chat_messages
-- Run this in your PostgreSQL database
ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_session_id_fkey;
ALTER TABLE chat_messages
ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;