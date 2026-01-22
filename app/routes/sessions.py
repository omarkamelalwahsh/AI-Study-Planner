"""
Session management API endpoints.
Implements CRUD operations for chat sessions.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.database import get_db
from app.models import ChatSession, ChatMessage
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Pydantic Schemas for Session API
# ============================================================

class SessionCreate(BaseModel):
    """Request to create a new session (body can be empty)."""
    pass


class SessionResponse(BaseModel):
    """Session response."""
    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """List sessions response."""
    sessions: List[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """Chat message response."""
    id: int
    role: str
    content: str
    created_at: datetime
    intent: Optional[str] = None
    
    class Config:
        from_attributes = True


class SessionMessagesResponse(BaseModel):
    """Session messages response."""
    session_id: str
    messages: List[MessageResponse]
    total: int


# ============================================================
# Session CRUD Endpoints
# ============================================================

@router.post("", response_model=SessionResponse)
async def create_session(db: AsyncSession = Depends(get_db)):
    """
    Create a new chat session.
    
    Returns:
        SessionResponse with session_id
    """
    session = ChatSession()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    logger.info(f"Created new session: {session.id}")
    
    return SessionResponse(
        session_id=str(session.id),
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    List all chat sessions with message counts.
    
    Args:
        limit: Max sessions to return (default 50)
        offset: Pagination offset
        
    Returns:
        List of sessions with metadata
    """
    # Get sessions with message counts
    stmt = (
        select(
            ChatSession,
            func.count(ChatMessage.id).label("message_count")
        )
        .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Get total count
    count_stmt = select(func.count(ChatSession.id))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    sessions = [
        SessionResponse(
            session_id=str(row.ChatSession.id),
            created_at=row.ChatSession.created_at,
            updated_at=row.ChatSession.updated_at,
            message_count=row.message_count
        )
        for row in rows
    ]
    
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific session by ID.
    
    Args:
        session_id: UUID of the session
        
    Returns:
        Session details with message count
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    stmt = (
        select(
            ChatSession,
            func.count(ChatMessage.id).label("message_count")
        )
        .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.id == session_uuid)
        .group_by(ChatSession.id)
    )
    
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=str(row.ChatSession.id),
        created_at=row.ChatSession.created_at,
        updated_at=row.ChatSession.updated_at,
        message_count=row.message_count
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a session and all its messages.
    
    Args:
        session_id: UUID of the session to delete
        
    Returns:
        Confirmation message
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    # Check if session exists
    stmt = select(ChatSession).where(ChatSession.id == session_uuid)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Delete messages first (foreign key constraint)
    delete_messages_stmt = delete(ChatMessage).where(ChatMessage.session_id == session_uuid)
    await db.execute(delete_messages_stmt)
    
    # Delete session
    delete_session_stmt = delete(ChatSession).where(ChatSession.id == session_uuid)
    await db.execute(delete_session_stmt)
    
    await db.commit()
    
    logger.info(f"Deleted session and messages: {session_id}")
    
    return {"message": "Session deleted successfully", "session_id": session_id}


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all messages for a session.
    
    Args:
        session_id: UUID of the session
        limit: Max messages to return
        offset: Pagination offset
        
    Returns:
        List of messages in chronological order
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    # Check session exists
    session_stmt = select(ChatSession).where(ChatSession.id == session_uuid)
    session_result = await db.execute(session_stmt)
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get messages
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_uuid)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # Get total count
    count_stmt = (
        select(func.count(ChatMessage.id))
        .where(ChatMessage.session_id == session_uuid)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    message_responses = [
        MessageResponse(
            id=msg.id,
            role=msg.role or "unknown",
            content=msg.content or "",
            created_at=msg.created_at,
            intent=msg.intent
        )
        for msg in messages
    ]
    
    return SessionMessagesResponse(
        session_id=session_id,
        messages=message_responses,
        total=total
    )
