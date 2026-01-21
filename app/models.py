import uuid
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text,
    CheckConstraint, UniqueConstraint, ARRAY, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict

from app.db import Base


# -----------------------------
# Core Catalog Tables
# -----------------------------

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

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=True)

    weeks = Column(Integer, nullable=False)
    hours_per_week = Column(Float, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

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
        UniqueConstraint("plan_id", "week_number", name="uq_plan_week"),
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
        UniqueConstraint("plan_week_id", "order_in_week", name="uq_week_order"),
    )


class CourseEmbedding(Base):
    __tablename__ = "course_embeddings"

    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), primary_key=True)
    model_name = Column(Text, primary_key=True)

    embedding = Column(ARRAY(Float), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


# -----------------------------
# Career Copilot Production Tables
# -----------------------------

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # IMPORTANT: JSONB must be MutableDict to detect in-place updates
    # IMPORTANT: default must be dict (callable), not {}
    state = Column(MutableDict.as_mutable(JSONB), default=dict, nullable=False)

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("state IS NOT NULL", name="chk_chat_session_state_not_null"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    # JSONB fields: MutableDict to detect in-place updates, default=dict if you ever set them
    intent_json = Column(MutableDict.as_mutable(JSONB), nullable=True)
    plan_output_json = Column(MutableDict.as_mutable(JSONB), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
        # Optional but recommended constraint to avoid junk roles:
        CheckConstraint("role IN ('user','assistant','system')", name="chk_chat_messages_role_valid"),
    )


class UserMemory(Base):
    __tablename__ = "user_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)

    key = Column(String, nullable=False)
    value = Column(MutableDict.as_mutable(JSONB), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_memory_key"),
    )


class SavedPlan(Base):
    __tablename__ = "saved_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True)

    plan_data = Column(MutableDict.as_mutable(JSONB), nullable=False)
    version = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
