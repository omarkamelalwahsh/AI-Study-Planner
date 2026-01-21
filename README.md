# Career Copilot RAG

Production-grade AI-powered career guidance system using Retrieval-Augmented Generation (RAG) with **Mixtral 8x7B** via Ollama.

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   React     │─────▶│   FastAPI    │─────▶│   Ollama    │
│  Frontend   │      │   Backend    │      │  (Mixtral)  │
│  (Port 3000)│      │  (Port 8001) │      │ (Port 11434)│
└─────────────┘      └──────┬───────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  PostgreSQL  │
                     │  (pgvector)  │
                     └──────────────┘
```

**Components**:

- **Frontend**: React + Vite for responsive UI with streaming chat
- **Backend**: FastAPI with async streaming support
- **LLM**: Mixtral 8x7B via Ollama (local, no API costs)
- **Embeddings**: multilingual-e5-small for semantic search
- **Vector DB**: FAISS for fast similarity search
- **Database**: PostgreSQL for conversation history and user data

---

## ⚙️ Production Configuration

### Required Environment Variables

Create a `.env` file in the project root with the following **required** variables:

```env
# Database (PostgreSQL) - REQUIRED
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/career_copilot

# LLM Provider - REQUIRED
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Optional: Embedding Model
EMBED_MODEL_NAME=intfloat/multilingual-e5-small
```

> **⚠️ IMPORTANT**: `DATABASE_URL` is mandatory in production. The application will fail fast if it's not set.

### Database Migrations

This project uses SQL migration scripts for schema management.

**To apply migrations:**

1. Ensure PostgreSQL is running and the database exists:

   ```powershell
   # Create database if it doesn't exist
   psql -U postgres -c "CREATE DATABASE career_copilot;"
   ```

2. Run the migration scripts in order:

   ```powershell
   # Apply production tables
   psql -U postgres -d career_copilot -f migrations/production_tables.sql
   
   # Apply persistence updates
   psql -U postgres -d career_copilot -f migrations/v3_persistence_updates.sql
   ```

### Testing

Run the persistence tests to verify the refactored chat backend:

```powershell
# Activate virtual environment
.\\venv\\Scripts\\Activate.ps1

# Install pytest if not already installed
pip install pytest pytest-asyncio

# Run persistence tests
python -m pytest tests/test_chat_persistence.py -v
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 14+**
- **Ollama** with Mixtral 8x7B model

### Step 1: Install Ollama & Pull Model

```powershell
# Install Ollama from https://ollama.ai
# After installation, pull the Mixtral model (~4.1GB download)
ollama pull mixtral:8x7b

# Verify installation
ollama list
```

### Step 2: Backend Setup

```powershell
# Navigate to project root
cd "E:\Career Copilot RAG"

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env if needed (defaults should work for local development)

# Initialize database and embeddings (sourced from data/courses.csv)
python scripts\ingest_courses.py


# Run the backend server
uvicorn app.main:app --reload --port 8001
```

Backend will be available at: **<http://localhost:8001>**

### Step 3: Frontend Setup

```powershell
# Open a new terminal
cd "E:\Career Copilot RAG\frontend"

# Install dependencies
npm install

# Setup environment (optional, defaults work)
cp .env.example .env

# Run development server
npm run dev -- --port 3000
```

Frontend will be available at: **<http://localhost:3000>**

---

## 📋 Environment Variables

### Backend (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider to use | `ollama` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name | `mixtral:8x7b` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://...` |
| `EMBED_MODEL_NAME` | Embedding model for semantic search | `intfloat/multilingual-e5-small` |
| `API_HOST` | Backend host | `0.0.0.0` |
| `API_PORT` | Backend port | `8001` |
| `ENABLE_MEMORY` | Enable conversation memory | `true` |
| `ENABLE_PDF` | Enable PDF export | `true` |
| `USE_RERANKER` | Use reranking for search results | `false` |

### Frontend (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API URL | `http://localhost:8001` |

---

## 🔌 API Reference

### Health Check

Check service status and configuration.

```http
GET /api/v1/health
```

**Response**:

```json
{
  "status": "ok",
  "service": "Career Copilot RAG",
  "version": "1.0.0",
  "llm_provider": "ollama",
  "ollama_url": "http://localhost:11434"
}
```

### Chat (Streaming)

Send a chat message and receive streaming response.

```http
POST /api/v1/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "I want to learn web development"}
  ],
  "model": "mixtral:8x7b"
}
```

**Response**: Server-Sent Events (SSE) stream

```
data: I'd
data:  be
data:  happy
data:  to
data:  help
data:  you
data:  with
data:  web
data:  development!
...
```

**Example using JavaScript**:

```javascript
const response = await fetch('http://localhost:8001/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: 'I want to learn Python' }
    ]
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  console.log(chunk); // Display incrementally
}
```

### API Documentation

Interactive API documentation is available at:

- **Swagger UI**: <http://localhost:8001/docs>
- **ReDoc**: <http://localhost:8001/redoc>

---

## 🧪 Verification Checklist

After setup, verify everything works:

- [ ] **Ollama Running**: `ollama list` shows `mixtral:8x7b`
- [ ] **Backend Health**: <http://localhost:8001/api/v1/health> returns 200 OK
- [ ] **Frontend Loads**: <http://localhost:3000> displays chat interface
- [ ] **API Docs**: <http://localhost:8001/docs> is accessible
- [ ] **Streaming Chat**: Send a message in UI, see typewriter effect
- [ ] **Course Recommendations**: Ask about careers, get relevant courses
- [ ] **No CORS Errors**: Check browser console (F12)
- [ ] **Database Connected**: No database errors in backend logs
- [ ] **Data Ingested**: `course_embeddings` table populated

---

## 🐛 Common Issues & Solutions

### Issue: "Connection refused" to Ollama

**Symptoms**: Backend errors mentioning connection to `localhost:11434`

**Solution**: Start Ollama service

```powershell
ollama serve
```

Or check if Ollama is running:

```powershell
# Test Ollama API
curl http://localhost:11434/api/tags
```

---

### Issue: CORS errors in browser console

**Symptoms**: `Access-Control-Allow-Origin` errors

**Solution**:

1. Verify `VITE_API_BASE_URL` in frontend `.env` matches backend URL
2. Ensure backend is running on port 8001
3. Check backend logs for CORS middleware initialization

---

### Issue: Slow response times

**Symptoms**: Chat responses take >30 seconds

**Solution**:

- **Hardware**: Mixtral 8x7B requires significant resources (8GB+ RAM, GPU recommended)
- **Alternative**: Use smaller model

  ```powershell
  ollama pull mixtral:7b
  ```

  Then update `.env`:

  ```
  OLLAMA_MODEL=mixtral:7b
  ```

- **Timeout**: Increase timeout in `app/llm/ollama.py` if needed

---

### Issue: Database connection errors

**Symptoms**: `could not connect to server` errors

**Solution**:

1. Verify PostgreSQL is running
2. Check `DATABASE_URL` in `.env`
3. Initialize database:

   ```powershell
   python scripts\init_db.py
   ```

---

### Issue: Module import errors

**Symptoms**: `ModuleNotFoundError` or `ImportError`

**Solution**:

```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

---

## 📚 Project Structure

```
E:\Career Copilot RAG\
├── app/                          # Backend application
│   ├── main.py                   # FastAPI app entrypoint
│   ├── api/routes/               # API endpoints
│   │   ├── chat.py               # Chat endpoint
│   │   └── health.py             # Health check
│   ├── core/                     # Core configuration
│   │   ├── config.py             # Settings (Pydantic)
│   │   ├── errors.py             # Error handlers
│   │   └── prompts.py            # System prompts
│   ├── llm/                      # LLM abstraction layer
│   │   ├── base.py               # BaseLLM interface
│   │   ├── factory.py            # LLM provider factory
│   │   └── ollama.py             # Ollama implementation
│   ├── services/                 # Business logic
│   │   ├── chat_service.py       # Chat orchestration
│   │   ├── retrieval_service.py  # DB Retrieval
│   │   └── state_machine.py      # Conversation state
│   ├── db/                       # Database layer
│   │   ├── database.py           # Connection & session
│   │   └── models.py             # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   │   ├── chat.py               # Chat models
│   │   ├── career_copilot.py     # Domain models
│   │   └── errors.py             # Error models
│   └── middleware/               # Middleware
│       └── logging.py            # Request logging
│
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── main.jsx              # Entrypoint
│   │   ├── App.jsx               # Main component
│   │   ├── api.js                # API client
│   │   └── index.css             # Styles
│   ├── package.json
│   └── vite.config.js
│
├── scripts/                      # Utility scripts
│   ├── init_db.py                # Database initialization
│   └── ingest_courses.py         # Course & Embedding ingestion
│
├── data/                         # Data files
│   └── courses.csv               # Course catalog
│
├── migrations/                   # Database migrations
├── tests/                        # Test suite
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Example configuration
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🔄 How Streaming Works

The chat endpoint uses **Server-Sent Events (SSE)** for real-time streaming:

1. **Client** sends POST request to `/api/v1/chat` with message history
2. **Backend** processes request:
   - Retrieves relevant courses from FAISS index
   - Constructs prompt with context
   - Streams request to Ollama
3. **Ollama** generates response token-by-token
4. **Backend** forwards each token to client immediately
5. **Frontend** displays tokens incrementally (typewriter effect)

**Benefits**:

- ✅ Lower perceived latency (user sees response immediately)
- ✅ Better UX for long responses
- ✅ Efficient resource usage (no buffering)
- ✅ Real-time feedback

---

## 🛠️ Development

### Running Tests

```powershell
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=app tests/
```

### Code Formatting

```powershell
# Format code with black
black app/

# Sort imports
isort app/

# Lint with flake8
flake8 app/
```

### Database Migrations

```powershell
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🚀 Production Deployment

### Backend

```powershell
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

### Frontend

```powershell
# Build for production
npm run build

# Serve with nginx or similar
```

### Environment

- Set `APP_ENV=production` in `.env`
- Use proper PostgreSQL credentials
- Configure firewall rules
- Set up SSL/TLS certificates
- Enable monitoring and logging

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📞 Support

For issues and questions:

- Check the [Common Issues](#-common-issues--solutions) section
- Review API docs at <http://localhost:8001/docs>
- Check backend logs for error details
- Verify all services are running (Ollama, PostgreSQL, Backend, Frontend)

---

## 🎯 Roadmap

- [ ] Add user authentication
- [ ] Implement conversation history UI
- [ ] Add course filtering and search
- [ ] Support for multiple LLM providers
- [ ] Add reranking for better search results
- [ ] PDF export for learning paths
- [ ] Mobile-responsive design improvements
- [ ] Add unit and integration tests
- [ ] Docker containerization
- [ ] CI/CD pipeline

---

**Built with ❤️ using FastAPI, React, and Ollama**
