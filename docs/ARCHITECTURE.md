# Career Copilot RAG - Architecture

## System Overview

Career Copilot is a Retrieval-Augmented Generation (RAG) agent designed to help users transition into new tech careers. It uses a semantic search engine to map user intent -> role requirements -> best-fit courses.

## Pipeline Steps

1. **Intent Classification**:
    * Input: User message.
    * Logic: Detects if user is asking for a roadmap, a specific course, or general advice.
    * Detects language (Arabic/English/Mixed).

2. **Role Retrieval (Role Graph)**:
    * The system queries a `Role Knowledge Base` to find required skills for the target role (e.g., "Data Scientist").
    * Output: A list of strict technical skills (e.g., "Python", "SQL", "Tableau").

3. **Course Retrieval (Semantic Search)**:
    * Uses `intfloat/multilingual-e5-small` to embed course descriptions.
    * Retrieves courses matching the required skills from the `courses` database.
    * Metadata filtering ensures level appropriateness (Beginner/Intermediate/Advanced).

4. **Plan Generation (The "Brain")**:
    * **Coverage Logic**:
        * `Our Courses`: System found internal courses for >70% of skills.
        * `Hybrid`: System found some internal courses, suggests external topics for others.
        * `Custom`: Few internal courses found, generates a study roadmap based on topics.
    * **Weekly Scheduler**: Distributes content over user-defined timeframe (e.g., 8 weeks).

5. **Response Composition**:
    * Generates a friendly response (Persona-based).
    * Returns a Structured JSON `PlanOutput` containing the roadmap, citations, and summary.

## Data Storage

* **PostgreSQL**:
  * `courses`: Catalog of courses.
  * `chat_sessions`: Chat history.
  * `chat_messages`: Individual interaction logs.
  * `plans`: Saved study plans.
  * `user_memory`: Key-value store for user preferences (if enabled).

* **FAISS / Vector Store**:
  * Stores dense embeddings of course content for fast retrieval.

## Frontend-Backend Integration

* **Vite/React Frontend** communicates with **FastAPI Backend**.
* State is managed via session IDs.
* Chat is "stateless" at the model level for each request, but history is retrieved from DB to form context.
