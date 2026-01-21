# 🚀 Career Copilot RAG

**Career Copilot** is a production-grade AI career assistant that helps users find personalized learning paths, courses, and career advice. It combines **RAG (Retrieval-Augmented Generation)** with the **Groq LLM API** (default: `llama-3.1-8b-instant`) to provide accurate, context-aware responses in English and Arabic.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![React](https://img.shields.io/badge/react-18+-61DAFB.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)

---

## ✨ Key Features

- **🧠 Intelligent RAG Engine**: Retrieves relevant courses from a curated dataset (`data/courses.csv`) to ground LLM responses.
- **💬 Dual-Language Support**: Native support for **English** and **Arabic (Egyptian Dialect)**.
- **🎯 Smart Intent Detection**: Automatically detects if a user wants to *learn a topic*, *find a specific course*, or *get career advice*.
- **🔎 Fuzzy Title Matching**: Finds courses even with typos or partial names (e.g., "Advansed Interpersnal").
- **⚡ Real-time Streaming**: Low-latency responses using server-sent events (SSE).
- **🎨 Modern UI**: Responsive React frontend with Dark/Light mode, beautiful typography, and smooth animations.

---

## 🏗️ Architecture Overview

The system consists of two main components:

1. **Backend (`app/`)**:
    - **Framework**: FastAPI
    - **LLM Provider**: Groq API (`llama-3.1-8b-instant` by default)
    - **Retrieval**: Pandas-based semantic & keyword search + Fuzzy matching (`difflib`).
    - **Database**: SQLite (for session persistence).

2. **Frontend (`frontend/`)**:
    - **Framework**: React (Vite)
    - **Styling**: Tailwind CSS
    - **State Management**: Zustand
    - **Icons**: Lucide React

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API Key

### 1. Clone & Setup Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Run the Application

We provided a convenient PowerShell script to run everything at once:

```powershell
./run_project.ps1
```

Or run manually:

**Backend:**

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## 📂 Project Structure

```
Career-Copilot-RAG/
├── app/                  # Backend Application
│   ├── api/              # API Routes (Chat, Health)
│   ├── core/             # Core Logic (Retrieval, Prompts)
│   ├── services/         # Business Logic (ChatService, LLM)
│   └── main.py           # Entry Point
├── frontend/             # React Frontend
│   ├── src/              # Components, Hooks, API
│   └── dist/             # Production Build
├── data/                 # Data Sources (Courses CSV, Lexicons)
├── docs/                 # Detailed Documentation
├── scripts/              # Maintenance Scripts
└── requirements.txt      # Python Dependencies
```

---

## 📚 Documentation

For more detailed information, check the `docs/` folder:

- [📖 API Reference](docs/API.md)
- [🛠️ Architecture Deep Dive](docs/ARCHITECTURE.md)
- [🚢 Deployment Guide](docs/DEPLOYMENT.md)

---

## 🤝 Contributing

Contributions are welcome! Please check the [Contributing Guide](docs/CONTRIBUTING.md).

---

## 🛡️ Security

This project implements standard security practices including:

- Input sanitization (Guardrails)
- CORS configuration
- Environment variable protection

---

**Built with ❤️ for Career Development**
