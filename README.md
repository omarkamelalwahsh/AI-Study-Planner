# Career Copilot RAG - Production System

**Production-grade bilingual RAG web application** for course recommendations using Groq LLM, FAISS vector search, and strict RAG-first architecture.

## 🎯 Core Principles

> **Golden Rule**: All user-facing responses MUST come from Groq LLM. No fallback responses except 503 "LLM unavailable".

**Pipeline**: User Input → Validation → Router → Retrieval → Groq Generator → Response

---

## 🚀 Quick Start (Local Setup)

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for frontend)
- Groq API key ([get one here](https://groq.com))

### 1. Backend Setup

```bash
# Clone and navigate
cd Career Copilot RAG

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY and DATABASE_URL
```

### 2. Database Setup

```bash
# Create database
createdb career_copilot

# Apply schema
psql -d career_copilot -f database/schema.sql
```

### 3. Data Ingestion

```bash
# Ingest courses and build FAISS index
python scripts/ingest_courses.py
```

### 4. Start Backend

```bash
# Development mode
uvicorn app.main:app --reload --port 8001

# Production mode
APP_ENV=prod uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 5. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Visit: **<http://localhost:3000>**

---

## 📁 Project Structure

```
Career Copilot RAG/
├── app/                      # Backend (FastAPI)
│   ├── routes/
│   │   ├── chat.py          # POST /chat endpoint
│   │   ├── health.py        # GET /health endpoint
│   │   └── courses.py       # Course endpoints
│   ├── router.py            # Intent classification (Groq)
│   ├── retrieval.py         # FAISS + exact matching
│   ├── generator.py         # Response generation (Groq)
│   ├── models.py            # ORM + Pydantic schemas
│   ├── database.py          # SQLAlchemy async
│   ├── config.py            # Settings
│   └── main.py              # FastAPI app
├── frontend/                # Frontend (Vite + React)
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API integration
│   │   └── styles/          # CSS
│   └── package.json
├── tests/                   # 15+ unit tests
│   ├── test_router_gating.py
│   ├── test_retrieval_accuracy.py
│   └── test_worst_case_scenarios.py
├── database/
│   └── schema.sql           # PostgreSQL schema
├── scripts/
│   └── ingest_courses.py    # Data ingestion
├── data/
│   ├── courses.csv          # Course catalog
│   ├── roles.jsonl          # Role mappings
│   ├── user_topic_lexicon.json
│   └── faiss_index/         # Generated FAISS index
├── requirements.txt
└── README.md
```

---
Get course details by ID.

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Coverage report
pytest --cov=app --cov-report=html

# Specific test suites
pytest tests/test_router_gating.py -v
pytest tests/test_retrieval_accuracy.py -v
pytest tests/test_worst_case_scenarios.py -v
```

**Test Coverage:**

- ✅ Router gating (7 intent classification tests)
- ✅ Retrieval accuracy (7 matching & ranking tests)
- ✅ Worst-case scenarios (8 error handling tests)

---

## 🔑 Environment Variables

```bash
# Application
APP_ENV=dev                   # dev | prod
API_HOST=0.0.0.0
API_PORT=8001

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/career_copilot

# LLM (Groq)
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Embeddings
EMBED_MODEL_NAME=intfloat/multilingual-e5-small

# Logging
LOG_LEVEL=info
```

---

## 🎨 Frontend

**Tech Stack:** Vite + React + TypeScript  
**Port:** 3000  
**Design:** Premium dark mode with glassmorphism

**Features:**

- Bilingual Arabic/English support (RTL)
- Real-time chat interface
- Course card rendering
- Session persistence
- Error handling (503 gracefully handled)
- Loading states

---

## 🛡️ Production Best Practices

✅ **Strict RAG-First**: No responses without LLM  
✅ **503 on LLM Failure**: No silent fallbacks  
✅ **No Hallucinations**: CourseDetails intent uses exact match only  
✅ **Intent Gating**: OUT_OF_SCOPE does no retrieval  
✅ **Retry Logic**: Exponential backoff on Groq rate limits  
✅ **Prompt Injection Defense**: Input validation  
✅ **Data Privacy**: Only log request_id, intent, count, latency  
✅ **CORS**: Strict in production, permissive in dev

---

## 📊 Intent Types

| Intent | Retrieval Method | Use Case |
|--------|------------------|----------|
| `COURSE_DETAILS` | Exact/fuzzy title match | "من بيشرح JavaScript?" |
| `SEARCH` | Semantic (top-10) | "عاوز أتعلم Python" |
| `CAREER_GUIDANCE` | Semantic (top-8) | "عايز أبقى Data Scientist" |
| `PLAN_REQUEST` | Semantic (top-8) | "خطة 8 أسابيع web developer" |
| `TITLE_UNKNOWN_SEARCH` | Semantic | "مش فاكر اسم الكورس" |
| `OUT_OF_SCOPE` | None | "ما أفضل فيلم؟" |
| `UNSAFE` | None | "أزاي أخترق..." |
| `SUPPORT_POLICY` | None | "كم سعر الكورس؟" |

---

## 🔧 Troubleshooting

**Issue**: `DATABASE_URL is not set`  
**Fix**: Copy `.env.example` to `.env` and configure DATABASE_URL

**Issue**: `Groq API unavailable`  
**Fix**: Verify GROQ_API_KEY is valid, check internet connection

**Issue**: `FAISS index not found`  
**Fix**: Run `python scripts/ingest_courses.py`

**Issue**: `Frontend can't reach API`  
**Fix**: Ensure backend running on port 8001, check VITE_API_BASE_URL

---

## 📄 License

MIT

---

## 🤝 Contributing

1. Run tests: `pytest tests/ -v`
2. Check code quality: `ruff check app/`
3. Format code: `black app/`

---

**Built with ❤️ using Groq LLM, FAISS, FastAPI, and React**
