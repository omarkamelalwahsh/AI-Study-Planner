# Career Copilot RAG - System Architecture

## Overview

Career Copilot RAG is an AI-powered career guidance system that uses a Retrieval-Augmented Generation (RAG) pipeline to recommend courses, analyze CVs, and provide career advice.

## Core Components

### 1. Backend API (FastAPI)

The backend is built with FastAPI and serves as the entry point for the frontend.

- **File**: `backend/main.py`
- **Port**: 8001 (Configured in `.env` and `config.py`)
- **Database**: SQLite (via SQLAlchemy) for session memory (`backend/database.py`, `backend/models.py`)

### 2. RAG Pipeline

The core logic resides in `backend/pipeline/` and executes a 7-step process for every user query:

#### Step 1: Intent Routing (`pipeline/intent_router.py`)

- Classifies user inputs into intents (e.g., `COURSE_SEARCH`, `CAREER_GUIDANCE`, `CV_ANALYSIS`).
- Handles ambiguity and clarification requests.
- **Key Model**: `IntentResult`

#### Step 2: Semantic Analysis (`pipeline/semantic_layer.py`)

- Deeply analyzes the query to extract:
  - **Primary Domain**: Core topic (e.g., "Web Development").
  - **Search Axes**: Keywords for retrieval.
  - **User Level**: Beginner/Intermediate/Advanced.
  - **Compound Queries**: Focus Area vs Tool (e.g., "Python" for "Data Science").

#### Step 3: Skill Extraction (`pipeline/skill_extractor.py`)

- Validates extracted skills against a curated `skills_catalog.csv`.
- Ensures no hallucinated skills are used for retrieval.

#### Step 4: Course Retrieval (`pipeline/retriever.py`)

- Retrieves relevant courses from `courses.csv` and `faiss_index` (if enabled).
- Strategies:
  - Skill-based retrieval (Primary).
  - Title/Category search (Fallback).
  - Semantic Vector Search (FAISS).

#### Step 5: Relevance Guard (`pipeline/relevance_guard.py`)

- Filters retrieved courses to ensure strict relevance.
- Applies checks like:
  - **Domain Enforcement**: Prevents cross-domain drift (e.g., Sales courses in a Coding query).
  - **Display Limits**: caps results for UI.

#### Step 6: Response Building (`pipeline/response_builder.py`)

- Generates the final natural language response.
- Constructs structured data for the UI:
  - **Course Cards**
  - **Skill Groups**
  - **Learning Plans**
  - **CV Dashboard**

#### Step 7: Consistency Check (`pipeline/consistency_check.py`)

- (Optional) Final validation of the response against the retrieved data.

## Data Sources

- **Courses**: `data/courses.csv`
- **Skills Catalog**: `data/skills_catalog_enriched_v2.csv`
- **Roles Knowledge Base**: `roles_kb.py` / `data/roles.jsonl`

## Frontend

- **Framework**: React + Vite + TypeScript
- **Styling**: Styled Components
- **State Management**: Zustand
- **Communication**: REST API (connecting to Backend)

## Directory Structure

```
/backend
  /pipeline    # Core RAG logic
  /llm         # LLM Client (Groq)
  /services    # File/Memory services
  /data        # CSV/JSON Data
/frontend
  /src/components # UI Components
```
