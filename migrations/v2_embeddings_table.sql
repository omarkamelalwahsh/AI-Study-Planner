-- Migration to add course_embeddings table
CREATE TABLE IF NOT EXISTS course_embeddings (
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding REAL [] NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, model_name)
);
CREATE INDEX IF NOT EXISTS course_embeddings_model_name_idx ON course_embeddings(model_name);