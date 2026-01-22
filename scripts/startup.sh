#!/bin/bash
# Production startup script for Career Copilot RAG

set -e

echo "========================================"
echo "Career Copilot RAG - Startup"
echo "========================================"

# Wait for PostgreSQL to be ready
echo "[1/5] Waiting for PostgreSQL..."
until PGPASSWORD=$DB_PASSWORD psql -h db -U postgres -d career_copilot -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "✓ PostgreSQL is ready"

# Apply database schema (idempotent - CREATE IF NOT EXISTS)
echo "[2/5] Applying database schema..."
PGPASSWORD=$DB_PASSWORD psql -h db -U postgres -d career_copilot -f /app/database/schema.sql
echo "✓ Schema applied"

# Check if data needs ingestion
echo "[3/5] Checking data ingestion status..."
COURSE_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h db -U postgres -d career_copilot -t -c "SELECT COUNT(*) FROM courses;")

if [ "$COURSE_COUNT" -eq 0 ]; then
    echo "No courses found - running ingestion..."
    python /app/scripts/ingest_courses.py
    echo "✓ Data ingestion complete"
else
    echo "✓ Found $COURSE_COUNT courses (skipping ingestion)"
fi

# Check if FAISS index exists
echo "[4/5] Checking FAISS index..."
if [ ! -f "/app/data/faiss_index/courses.faiss" ]; then
    echo "FAISS index not found - will be created on first API request"
else
    echo "✓ FAISS index found"
fi

# Start API server
echo "[5/5] Starting API server..."
echo "========================================"
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
