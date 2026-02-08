
# Career Copilot RAG (Production V2.0) 🚀

An AI-powered career guidance assistant that uses a **7-Step RAG (Retrieval-Augmented Generation)** architecture to provide personalized course recommendations, career roadmaps, and CV analysis.

This system is designed to be **Deterministic & Data-Driven**, ensuring that recommendations are always grounded in the verified `courses.csv` catalog while leveraging LLMs for natural language understanding and dynamic explanations.

---

## 🌟 Key Features

### 1. Smart Exploration Flow (V2.0)

For users who are "lost" or unsure where to start.

- **Fast Path**: Auto-detects "I want a job" intent and skips directly to domain selection.
- **Guided Discovery**: Refines choices (Goal → Interest → Track → Results).
- **Interactive UI**: Uses choice buttons to reduce friction (No typing needed for standard paths).
- **Zero Hallucinations**: All domains and tracks are mapped strictly to the catalog.

### 2. CV Analysis Engine 📄

Deep analysis of uploaded resumes (PDF/DOCX/Image).

- **Scoring**: Calculates an overall score (0-100) based on skills, experience, and market readiness.
- **Gap Analysis**: Identifies missing skills relative to the target role.
- **Smart Recommendations**: Suggests specific courses and **Portfolio Projects** to fill gaps.
- **Dashboard UI**: Displays results in a visual dashboard with charts and checklists.

### 3. RAG Course Search 🔍

The core recommendation engine.

- **Skill Extraction**: Maps user queries to canonical skills (e.g., "React" → "Frontend Development").
- **Hybrid Retrieval**: Combines semantic search (vector) and keyword search.
- **Relevance Guard**: A rigorous filter that removes irrelevant courses even if they match keywords (e.g., distinguishing "Java" from "JavaScript").

### 4. Dynamic Learning Plans 📅

Generates structured daily/weekly study schedules.

- **Slot Filling**: Asks for duration (e.g., "1 month") and daily availability (e.g., "2 hours").
- **Adaptive**: Adjusts intensity based on the user's constraints.

---

## 🏗️ Architecture: The 7-Step Pipeline

The backend (`/backend`) processes every request through this pipeline:

1. **Intent Router**: Classifies user intent (Search, Exploration, CV, etc.).
2. **Semantic Layer**: Understands context, extracted entities, and previous conversation history.
3. **Skill Extractor**: Validates extracted terms against the `skills_master_list`.
4. **Retriever**: Fetches candidates from the `courses.csv` catalog.
5. **Relevance Guard**: Filters out false positives using strict heuristics.
6. **Consistency Checker**: Ensures the final response matches the retrieved data (Anti-Hallucination).
7. **Response Builder**: Assembles the final JSON response (Text, Courses, Dashboard, etc.).

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Pandas, OpenAI/Groq API (LLM).
- **Frontend**: React, TypeScript, Vite, CSS Modules.
- **Data**: CSV-based Catalog (`data/courses.csv`) for easy updates.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 16+
- PostgreSQL (Optional, for persistent memory)

### 1. Environment Setup

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Data Updates

To add new courses, simply edit `backend/data/courses.csv`. The system automatically detects new categories and tracks on the next restart.

---

## ✅ Recent Updates (What's New)

- **Exploration Flow Fix**: Fixed "hanging" states where the bot didn't show buttons.
- **Fast Path**: "I want to work" now jumps straight to domain selection.
- **Design Tracks**: Improved sub-track mapping for "Design" (Graphic, UI/UX, etc.).
- **Language Persistence**: The bot now locks to the user's language (Arabic/English).
- **Frontend Buttons**: Fixed rendering of `ChoiceQuestion` options in the chat UI.
- **Immediate Results**: The flow now transitions directly from selection to results without extra turns.
