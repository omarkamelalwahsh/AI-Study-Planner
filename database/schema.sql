-- Career Copilot RAG Database Schema
-- PostgreSQL 14+
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Courses table (main catalog)
CREATE TABLE IF NOT EXISTS courses (
    course_id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(200),
    level VARCHAR(50),
    duration_hours DECIMAL(10, 2),
    skills TEXT,
    description TEXT,
    instructor VARCHAR(200),
    cover TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Indexes for efficient retrieval
CREATE INDEX IF NOT EXISTS idx_courses_title ON courses USING btree (LOWER(title));
CREATE INDEX IF NOT EXISTS idx_courses_category ON courses (category);
CREATE INDEX IF NOT EXISTS idx_courses_level ON courses (level);
CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses (instructor);
-- Full-text search index for title and description
CREATE INDEX IF NOT EXISTS idx_courses_fts ON courses USING gin(
    to_tsvector(
        'english',
        coalesce(title, '') || ' ' || coalesce(description, '')
    )
);
-- Course embeddings table (for vector search metadata)
CREATE TABLE IF NOT EXISTS course_embeddings (
    id SERIAL PRIMARY KEY,
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    embedding_model VARCHAR(200) NOT NULL,
    chunk_text TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_id, embedding_model)
);
CREATE INDEX IF NOT EXISTS idx_course_embeddings_course_id ON course_embeddings (course_id);
-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Chat messages table (optional - for logging and telemetry)
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    request_id UUID DEFAULT uuid_generate_v4(),
    user_message_hash VARCHAR(64),
    -- SHA256 hash for privacy
    intent VARCHAR(50),
    retrieved_course_count INTEGER,
    response_length INTEGER,
    latency_ms INTEGER,
    error_occurred BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_intent ON chat_messages (intent);
CREATE INDEX IF NOT EXISTS idx_chat_messages_error ON chat_messages (error_occurred)
WHERE error_occurred = TRUE;
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = CURRENT_TIMESTAMP;
RETURN NEW;
END;
$$ language 'plpgsql';
-- Trigger for courses table
DROP TRIGGER IF EXISTS update_courses_updated_at ON courses;
CREATE TRIGGER update_courses_updated_at BEFORE
UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
-- Trigger for chat_sessions table  
DROP TRIGGER IF EXISTS update_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_sessions_updated_at BEFORE
UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();