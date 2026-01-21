# API Documentation

Base URL: `http://localhost:8000`

## Core

### `GET /health`

Returns `{"status": "ok"}`. Used for liveness probes.

### `GET /ready`

Detailed readiness check. Verifies:

1. Database connection.
2. Search index loaded.
Returns `503` if not ready.

## Career Copilot (Chat)

### `POST /career-copilot`

Main conversation endpoint.

* **Body**: `CareerCopilotRequest`
  * `message`: User text.
  * `session_id`: UUID (optional, for continuity).
  * `constraints`: `{ "weekly_hours": 10, ... }`
* **Response**: `PlanOutput`
  * `summary`: Text response.
  * `plan_weeks`: Structured weekly schedule.

## Sessions

### `POST /sessions`

Create a new chat session.

* **Body**: `{"title": "optional"}`
* **Response**: `{"id": "uuid", ...}`

### `GET /sessions/{id}/messages`

Retrieve message history.

## Memory (Opt-in)

### `POST /memory`

Save a user preference.

* **Body**: `{"key": "preferred_role", "value": "Data Scientist", "user_id": "uuid"}`

### `DELETE /memory/{id}`

Remove a memory item.
