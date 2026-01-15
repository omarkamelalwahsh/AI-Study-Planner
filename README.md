# Career Copilot RAG 🎓

**A Full-Stack AI Career Advisor** that generates personalized study plans and course recommendations.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-production-green)

## Overview

Career Copilot helps users transition into new tech roles (Data Science, Software Engineering, AI) by mapping their career goals to specific skills and recommending actual courses from an internal catalog. It uses **Retrieval-Augmented Generation (RAG)** to ensure recommendations are grounded in reality, not hallucinated.

## Features

* **Semantic Search**: Finds relevant courses even if keywords don't match exactly.
* **Structured Study Plans**: Generates week-by-week schedules (goals, topics, practice).
* **Multilingual Support**: Fully supports Arabic (RTL) and English.
* **Session Management**: Persistent chat history with PostgreSQL.
* **PDF Export**: Download your study plan as a PDF.
* **No Hallucinations (Strict Mode)**: "Our Courses" mode prioritizes internal catalog content.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a deep dive.

1. **Backend**: FastAPI (Python) + SQLAlchemy.
2. **Database**: PostgreSQL (Data) + FAISS (Vector Index).
3. **Frontend**: React + Vite (TypScript).

## Getting Started

### Prerequisites

* Python 3.10+
* Node.js 18+ (for frontend)
* PostgreSQL 14+

### Installation

1. **Clone the repository**:

    ```bash
    git clone https://github.com/your-org/career-copilot-rag.git
    cd career-copilot-rag
    ```

2. **Setup Environment**:
    copy `.env.example` to `.env` and update `DATABASE_URL`.

    ```bash
    cp .env.example .env
    ```

3. **Backend Setup**:

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```

4. **Database Upgrade**:

    ```bash
    # Initialize Schema
    python scripts/init_db.py
    # Ingest Sample Data
    python scripts/indexing/ingest_courses.py
    # Build Search Index
    python scripts/indexing/build_index.py
    ```

5. **Run Backend**:

    ```bash
    uvicorn app.main:app --reload
    ```

    API will be available at `http://localhost:8000`.

6. **Run Frontend** (if present):

    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## Development

### Running Tests

```bash
pytest
```

### Formatting

```bash
black .
ruff check .
```

## API Documentation

See [docs/API.md](docs/API.md) for endpoint details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
