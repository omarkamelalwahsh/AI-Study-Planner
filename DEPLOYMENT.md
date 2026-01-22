"""
Quick Start Deployment Guide

Follow these steps in order to deploy the RAG-first system.
"""

# ============================================================================

# STEP 1: PRE-FLIGHT CHECKLIST

# ============================================================================

"""
Before you begin, ensure you have:

✅ Python 3.10+ installed
✅ PostgreSQL 14+ installed and running
✅ Groq API key (sign up at console.groq.com if needed)
✅ Git (for version control)
✅ 2GB free disk space (for embeddings model)
"""

# ============================================================================

# STEP 2: INSTALL DEPENDENCIES

# ============================================================================

"""

# Create virtual environment (recommended)

python -m venv venv

# Activate virtual environment

# Windows

venv\Scripts\activate

# Linux/Mac

source venv/bin/activate

# Install dependencies

pip install -r requirements.txt

# This will download (~5 minutes first time)

# - sentence-transformers model (~90MB)

# - FAISS library

# - All Python packages

"""

# ============================================================================

# STEP 3: CONFIGURE ENVIRONMENT

# ============================================================================

"""

# Edit .env file

# Set your Groq API key (CRITICAL - system won't start without this in prod)

GROQ_API_KEY=gsk_your_actual_groq_api_key_here

# Verify database URL is correct

DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/career_copilot

# For production

APP_ENV=prod
LOG_LEVEL=INFO
"""

# ============================================================================

# STEP 4: DATABASE SETUP

# ============================================================================

"""

# Create PostgreSQL database

createdb career_copilot

# Apply schema

psql -d career_copilot -f database/schema.sql

# Verify tables created

psql -d career_copilot -c "\dt"

# Expected output

# Schema |       Name        | Type  |  Owner

# --------+-------------------+-------+---------

# public | chat_messages     | table | postgres

# public | course_embeddings | table | postgres

# public | courses           | table | postgres

"""

# ============================================================================

# STEP 5: INGEST DATA

# ============================================================================

"""

# Run ingestion script

python scripts/ingest_courses.py

# Expected output

# [1/5] Loading CSV data

# ✓ Loaded 312 courses from CSV

#

# [2/5] Inserting courses into database

# ✓ Inserted 312 courses into database

#

# [3/5] Generating embeddings

# Loading embedding model: intfloat/multilingual-e5-small

# Generating embeddings for 312 courses

# 100%|████████████████████████████████| 312/312

# ✓ Generated 312 embeddings

#

# [4/5] Building FAISS index

# ✓ FAISS index saved: data/faiss_index/index.faiss

# ✓ Index contains 312 vectors

#

# [5/5] Storing embedding metadata

# ✓ Stored 312 embedding metadata records

#

# ✓ Ingestion complete

# Verify FAISS index created

ls data/faiss_index/

# Expected files

# - index.faiss

# - index_mapping.pkl

"""

# ============================================================================

# STEP 6: START SERVER

# ============================================================================

"""

# Development mode (auto-reload on code changes)

uvicorn app.main:app --reload --port 8001

# Production mode

APP_ENV=prod uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4

# Expected startup logs

# INFO: Starting Career Copilot RAG API (env: prod)

# INFO: ✓ Groq API key configured

# INFO: Loading vector store

# INFO: Loading embedding model: intfloat/multilingual-e5-small

# INFO: Loading FAISS index from: data/faiss_index/index.faiss

# INFO: FAISS index loaded: 312 vectors

# INFO: Application startup complete

# INFO: Uvicorn running on <http://0.0.0.0:8001>

"""

# ============================================================================

# STEP 7: VERIFY DEPLOYMENT

# ============================================================================

"""

# Test 1: Health check

curl <http://localhost:8001/health>

# Expected response

{
  "status": "ok",
  "database": "connected",
  "groq_api_key": "configured",
  "vector_store": "loaded",
  "course_count": 312
}

# ✅ If all fields show "ok"/"connected"/"loaded", proceed to next test

# Test 2: Simple chat query

curl -X POST <http://localhost:8001/chat> \
  -H "Content-Type: application/json" \
  -d '{"message": "Who teaches Python?"}'

# Expected response (example)

{
  "response": "إليك كورسات Python المتاحة:\n• Python Database — Intermediate — Data Security — Zedny Production\n...",
  "intent": "SEARCH",
  "course_count": 4
}

# ✅ If you get a response with courses, deployment successful

"""

# ============================================================================

# STEP 8: RUN "DEFINITION OF DONE" TESTS

# ============================================================================

"""

# Run all 10 required test scenarios

# See: tests/test_scenarios_definition_of_done.py

# Quick smoke test (must PASS)

curl -X POST <http://localhost:8001/chat> \
  -H "Content-Type: application/json" \
  -d '{"message": "اقترحلي فيلم"}'

# Expected: OUT_OF_SCOPE with NO course recommendations

# If this passes, run the remaining 9 tests in test_scenarios_definition_of_done.py

"""

# ============================================================================

# TROUBLESHOOTING

# ============================================================================

"""
Issue: "GROQ_API_KEY is missing"
Solution: Edit .env and set your Groq API key

Issue: "Database connection failed"
Solution:

  1. Verify PostgreSQL is running: pg_ctl status
  2. Check DATABASE_URL in .env
  3. Test connection: psql -d career_copilot

Issue: "FAISS index not found"
Solution: Run python scripts/ingest_courses.py

Issue: "ImportError: No module named 'app'"
Solution:

  1. Ensure you're in the project root directory
  2. Activate virtual environment: venv\Scripts\activate
  3. Reinstall: pip install -r requirements.txt

Issue: Health check shows "vector_store": "not_loaded"
Solution:

  1. Check data/faiss_index/index.faiss exists
  2. Re-run ingestion: python scripts/ingest_courses.py
  3. Restart server

Issue: 503 errors on all queries
Solution:

  1. Verify Groq API key is valid (not placeholder)
  2. Check Groq API status: <https://status.groq.com>
  3. Check logs for specific error: tail -f app.log
"""

# ============================================================================

# PRODUCTION DEPLOYMENT (Cloud/Server)

# ============================================================================

"""
For cloud deployment (AWS, Azure, GCP):

1. Environment Variables:
   - Set GROQ_API_KEY via secrets manager (NOT .env file)
   - Set DATABASE_URL to production PostgreSQL
   - Set APP_ENV=prod
   - Set LOG_LEVEL=INFO

2. Database:
   - Use managed PostgreSQL (RDS, Cloud SQL, Azure Database)
   - Enable connection pooling
   - Set up automated backups

3. Application Server:
   - Use gunicorn with uvicorn workers:
     gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
   - Set up reverse proxy (nginx/Caddy)
   - Enable HTTPS (Let's Encrypt)

4. Monitoring:
   - Set up error tracking (Sentry)
   - Monitor Groq API usage/rate limits
   - Set up alerts for 503 errors

5. Scaling:
   - Vector store loads once at startup (shared across workers)
   - Horizontal scaling: multiple app instances behind load balancer
   - Database: connection pooling + read replicas

6. CI/CD:
   - Run tests in CI: pytest tests/
   - Build Docker image
   - Deploy to staging → manual tests → deploy to prod
"""

# ============================================================================

# NEXT STEPS

# ============================================================================

"""
After successful deployment:

1. ✅ Monitor production logs for errors
2. ✅ Track key metrics:
   - Average latency (<3s target)
   - 503 error rate (<1% target)
   - OUT_OF_SCOPE rate (monitor for abuse)
3. ✅ Set up alerts for:
   - Groq API failures (>10 consecutive)
   - Database connection errors
   - High latency (>5s)
4. ✅ Plan for updates:
   - Course catalog updates (re-run ingestion)
   - Groq model upgrades
   - Prompt refinements based on user feedback
5. ✅ Consider future enhancements:
   - Frontend UI (Vite)
   - Rate limiting
   - Chat history persistence
   - Analytics dashboard
"""
