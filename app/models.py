"""
Data models (Pydantic schemas and SQLAlchemy ORM).
"""
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DECIMAL, TIMESTAMP, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Optional, List, Literal
from datetime import datetime
from app.database import Base
import uuid


# ============================================================
# SQLAlchemy ORM Models
# ============================================================

class Course(Base):
    """Course catalog table."""
    __tablename__ = "courses"
    
    course_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    category = Column(String(200))
    level = Column(String(50))
    duration_hours = Column(DECIMAL(10, 2))
    skills = Column(Text)
    description = Column(Text)
    instructor = Column(String(200))
    cover = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class CourseEmbedding(Base):
    """Course embeddings metadata table."""
    __tablename__ = "course_embeddings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(UUID(as_uuid=True), nullable=False)
    embedding_model = Column(String(200), nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding_meta = Column("metadata", JSONB)  # Renamed attribute to avoid SQLAlchemy conflict
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class ChatSession(Base):
    """Chat session table."""
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_memory = Column(JSONB, default=dict)


class ChatMessage(Base):
    """Chat message logging table."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)  # Optional link to session
    request_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Actual message content
    user_message_hash = Column(String(64))
    intent = Column(String(50))
    retrieved_course_count = Column(Integer)
    response_length = Column(Integer)
    latency_ms = Column(Integer)
    error_occurred = Column(Boolean, default=False)
    error_type = Column(String(100))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


# ============================================================
# Pydantic Schemas (API Request/Response)
# ============================================================

class CourseSchema(BaseModel):
    """Course response schema."""
    course_id: str | uuid.UUID
    title: str
    category: Optional[str] = None
    level: Optional[str] = None
    duration_hours: Optional[float] = None
    skills: Optional[str] = None
    description: Optional[str] = None
    instructor: Optional[str] = None
    cover: Optional[str] = None
    
    class Config:
        from_attributes = True


class RouterOutput(BaseModel):
    """Router intent classification output with scope gating."""
    in_scope: bool
    intent: Literal[
        "GREETING",
        "COURSE_DETAILS",
        "SEARCH",
        "SKILL_SEARCH",
        "CATEGORY_BROWSE",
        "AVAILABILITY_CHECK",
        "FOLLOW_UP",
        "CAREER_GUIDANCE",
        "PLAN_REQUEST",
        "OUT_OF_SCOPE",
        "UNSAFE",
        "SUPPORT_POLICY"
    ]
    target_categories: List[str] = Field(default_factory=list)
    course_title_candidate: Optional[str] = None
    english_search_term: Optional[str] = None
    
    # New fields for 7-step pipeline
    # Minimal routing metadata
    user_goal: Optional[str] = None
    target_role: Optional[str] = None
    role_type: Literal["technical", "non_technical", "mixed"] = "non_technical"
    user_language: Literal["ar", "en", "mixed"] = "ar"
    search_scope: Literal["ALL_CATEGORIES", "CATEGORY_RESTRICTED"] = "ALL_CATEGORIES"
    
    keywords: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Chat endpoint request."""
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=500)


class CourseDetail(BaseModel):
    """Course detail in response."""
    course_id: str
    title: str
    level: Optional[str] = None
    category: Optional[str] = None
    instructor: Optional[str] = None
    duration_hours: Optional[float] = None
    description: Optional[str] = None
    skills: Optional[str] = None
    cover: Optional[str] = None


class ErrorDetail(BaseModel):
    """Error detail object."""
    code: str
    message: str


class ChatResponse(BaseModel):
    """Chat endpoint response (master prompt API contract)."""
    session_id: str
    intent: str
    answer: str
    courses: List[CourseDetail] = Field(default_factory=list)
    error: Optional[ErrorDetail] = None
    request_id: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["ok", "degraded"]
    database: Literal["connected", "error"]
    groq_api_key: Literal["configured", "missing"]
    vector_store: Literal["loaded", "not_loaded"]
    course_count: int = 0
