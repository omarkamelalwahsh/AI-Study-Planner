# Career Copilot RAG - API Reference

## Base URL

`http://localhost:8001` (Default)

## Endpoints

### 1. Chat & Guidance

**POST** `/chat`

Primary endpoint for all RAG interactions (Career advice, Course search, etc.).

**Request Body:**

```json
{
  "message": "I want to learn Python",
  "session_id": "optional-uuid-string"
}
```

**Response:**

```json
{
  "session_id": "uuid",
  "intent": "COURSE_SEARCH",
  "answer": "Here are some recommended Python courses...",
  "courses": [
    {
      "course_id": "123",
      "title": "Python for Data Science",
      "level": "Beginner",
      "instructor": "John Doe",
      "reason": "Matches your interest in Data Science"
    }
  ],
  "skill_groups": [],
  "learning_plan": null
}
```

### 2. CV Analysis

**POST** `/upload-cv`

Upload a CV (PDF/DOCX) for analysis and recommendations.

**Form Data:**

- `file`: (Binary) The CV file.
- `session_id`: (String, Optional)

**Response:**
Similar to `/chat`, but includes `dashboard` data for CV visualizations.

### 3. System Health

**GET** `/health`

Returns system status and loaded data stats.

**Response:**

```json
{
  "status": "healthy",
  "service": "career-copilot-rag",
  "version": "2.0.0",
  "data_loaded": true,
  "semantic_search": true,
  "roles_loaded": true
}
```

### 4. Metadata

**GET** `/roles`
Returns list of supported job roles.

**GET** `/categories`
Returns list of course categories.
