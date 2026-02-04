# Career Copilot RAG - Developer Guide

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (Optional, defaults to SQLite)
- Groq API Key

### 1. Backend Setup

The backend relies on the `backend/` directory being the working directory for correct import resolution.

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv env
# Windows:
.\env\Scripts\activate
# Mac/Linux:
source env/bin/activate

# 3. Install Dependencies
pip install -r requirements.txt

# 4. Environment Variables
# Create .env file based on .env.example
copy example.env .env
```

#### ⚠️ Common Startup Errors

**Error**: `ModuleNotFoundError: No module named 'config'`

- **Cause**: Running from the root directory (`H:\Career Copilot RAG> uvicorn backend.main:app`).
- **Fix**: You must `cd backend` first.

**Error**: `ModuleNotFoundError: No module named 'backend'`

- **Cause**: Running `uvicorn backend.main:app` *inside* the backend folder.
- **Fix**: Remove the package prefix. Use `uvicorn main:app`.

#### ✅ Correct Command to Run Server

```bash
# Make sure you are in /backend
uvicorn main:app --reload --port 8001
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## 🧪 Testing

### Running Tests

The project includes several test scripts in the root directory and `backend/` directory.

```bash
# Run backend logic tests
cd backend
python -m pytest
```

### Manual API Testing

Once the server is running, visit the Swagger UI docs:
[http://localhost:8001/docs](http://localhost:8001/docs)

## 📦 Project Structure Details

- **`backend/main.py`**: Entry point. Defined `app` object.
- **`backend/config.py`**: Loads env vars.
- **`backend/pipeline/`**: Logic for RAG (Intent, Retrieval, Response).
- **`backend/data/`**: Static CSV data.

## 🛠️ Contribution Workflow

1. Create a branch for your feature.
2. Ensure `test_logic.py` passes (if relevant).
3. document any new env vars in `.env.example`.
