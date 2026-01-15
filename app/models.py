import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint, UniqueConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import cast
from app.db import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_idx = Column(Integer, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    level = Column(Text, nullable=True)
    duration_hours = Column(Float, nullable=True)
    skills = Column(Text, nullable=True)
    instructor = Column(Text, nullable=True)
    cover = Column(Text, nullable=True)
    url = Column(Text, nullable=True)

class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    raw_query = Column(Text, nullable=False)
    normalized_query = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=True)
    weeks = Column(Integer, nullable=False)
    hours_per_week = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    weeks_obj = relationship("PlanWeek", back_populates="plan", cascade="all, delete-orphan")
    query = relationship("SearchQuery")

class PlanWeek(Base):
    __tablename__ = "plan_weeks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    week_number = Column(Integer, nullable=False)

    plan = relationship("Plan", back_populates="weeks_obj")
    items = relationship("PlanItem", back_populates="week", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('plan_id', 'week_number', name='uq_plan_week'),
    )

class PlanItem(Base):
    __tablename__ = "plan_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_week_id = Column(UUID(as_uuid=True), ForeignKey("plan_weeks.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    order_in_week = Column(Integer, nullable=False)

    week = relationship("PlanWeek", back_populates="items")
    course = relationship("Course")

    __table_args__ = (
        UniqueConstraint('plan_week_id', 'order_in_week', name='uq_week_order'),
    )

from sqlalchemy.dialects.postgresql import UUID, JSONB

class CourseEmbedding(Base):
    __tablename__ = "course_embeddings"

    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), primary_key=True)
    model_name = Column(Text, primary_key=True)
    embedding = Column(ARRAY(Float), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- Career Copilot Production Models ---

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    intent_json = Column(JSONB, nullable=True)
    plan_output_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

class UserMemory(Base):
    __tablename__ = "user_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint('user_id', 'key', name='uq_user_memory_key'),)

class SavedPlan(Base):
    __tablename__ = "saved_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True)
    plan_data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
