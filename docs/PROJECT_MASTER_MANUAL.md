# Career Copilot RAG - Complete Implementation Manual

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Developer Guide & Setup](#developer-guide--setup)
4. [API Reference](#api-reference)

---

## 1. Project Overview

**Career Copilot RAG** is an AI-powered career guidance and course recommendation system. It uses a Retrieval-Augmented Generation (RAG) architecture to help users find the best programming courses, analyze their CVs, and generate personalized learning plans.

### ✨ Key Features

- **🎯 Intelligent Course Search**: Semantically understands requests like "I want to be a Data Scientist" or "Learn React".
- **📄 CV Analysis**: Upload a PDF/DOCX CV to get a skills gap analysis and role recommendations.
- **🗺️ Learning Plans**: Generates structured weekly schedules for mastering new skills.
- **🧠 Contextual Memory**: Remembers your previous questions for natural conversation.
- **🏢 Catalog-Grounded**: Strictly recommends courses from the verified catalog to prevent hallucinations.

---

## 2. System Architecture

### Core Components

#### 1. Backend API (FastAPI)

- **File**: `backend/main.py`
- **Default Port**: **8001**
- **Database**: SQLite (via SQLAlchemy) for session memory.

#### 2. The 7-Step RAG Pipeline

The core logic in `backend/pipeline/` executes this process for every query:

1. **Intent Routing** (`pipeline/intent_router.py`):
    - Classifies user inputs (e.g., `COURSE_SEARCH`, `CV_ANALYSIS`).
2. **Semantic Analysis** (`pipeline/semantic_layer.py`):
    - Extracts domains, search axes, and user level.
3. **Skill Extraction** (`pipeline/skill_extractor.py`):
    - Validates skills against `skills_catalog.csv`.
4. **Course Retrieval** (`pipeline/retriever.py`):
    - Searches `courses.csv` using skill matching and vector search (FAISS).
5. **Relevance Guard** (`pipeline/relevance_guard.py`):
    - Strict filtering to prevent domain drift (e.g., hiding Sales courses from Devs).
6. **Response Building** (`pipeline/response_builder.py`):
    - Generates natural language answers and structured UI data.
7. **Consistency Check** (`pipeline/consistency_check.py`):
    - Final validation.

---

## 3. Developer Guide & Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### 📥 Backend Setup

**CRITICAL**: You must run commands from the `backend/` directory.

```bash
# 1. Navigate to backend
cd backend

# 2. Setup Venv
python -m venv env
source env/bin/activate  # Windows: .\env\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Start Server (Port 8001)
uvicorn main:app --reload --port 8001
```

> **⚠️ Common Error**: `ModuleNotFoundError: No module named 'backend'`
> **Fix**: Do not use `backend.main:app`. Use `main:app` while inside the backend folder.

### 🎨 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

App available at: `http://localhost:3000`

---

## 4. API Reference

**Base URL**: `http://localhost:8001`

### `/chat` (POST)

Primary endpoint for interactions.

- **Body**: `{"message": "I want to learn Python", "session_id": "optional"}`
- **Returns**: Intent, Answer, Courses list, Learning Plan.

### `/upload-cv` (POST)

CV Analysis endpoint.

- **Body**: Form-data with `file`.
- **Returns**: Skills analysis, Dashboard data, Role fit.

### `/health` (GET)

System status check.
