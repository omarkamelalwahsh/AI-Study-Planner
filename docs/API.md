# API Reference

This document details the REST API endpoints available in the Career Copilot RAG backend.

**Base URL**: `http://localhost:8000/api/v1`

## 🩺 System

### Health Check

`GET /health`
Returns the status of the API and its dependencies.

**Response:**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "development"
}
```

---

## 💬 Chat

### Send Message

`POST /chat`
Main endpoint for interacting with the RAG chatbot. Supports specialized intent detection (learning paths, course recommendations, general advice).

**Request Body:**

```json
{
  "messages": [
    { "role": "user", "content": "I want to learn Python" }
  ],
  "session_id": "uuid-string",
  "client_state": {
    "last_topic": "string (optional)",
    "last_courses": []
  }
}
```

**Response (JSON):**

```json
{
  "message": "Here is a Python learning path...",
  "courses": [
    {
      "course_id": "123",
      "title": "Python for Beginners",
      "level": "Beginner",
      "category": "Programming",
      "instructor": "John Doe",
      "duration_hours": 10.5
    }
  ],
  "study_plan": [],
  "client_state": { ... }
}
```

---

## 🛑 Error Handling

The API returns standard HTTP error codes:

- `400 Bad Request`: Validation errors or missing input.
- `404 Not Found`: Resource not found.
- `503 Service Unavailable`: Backend service (LLM/DB) issues.
