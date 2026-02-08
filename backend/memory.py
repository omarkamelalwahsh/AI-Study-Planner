"""
Career Copilot RAG Backend - Conversation Memory
Stores and retrieves conversation history for context-aware responses.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class Conversation:
    """A conversation session with message history."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_intent: Optional[str] = None
    last_role: Optional[str] = None
    last_topic: Optional[str] = None
    last_skills: List[str] = field(default_factory=list)
    state: Dict = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: dict = None):
        """Add a message to the conversation."""
        self.messages.append(Message(
            role=role,
            content=content,
            metadata=metadata or {}
        ))
    
    def get_context(self, max_messages: int = 6) -> str:
        """Get recent conversation context as a formatted string."""
        if not self.messages:
            return ""
        
        recent = self.messages[-max_messages:]
        context_parts = []
        
        for msg in recent:
            role_label = "المستخدم" if msg.role == "user" else "المساعد"
            context_parts.append(f"{role_label}: {msg.content[:200]}")
        
        return "\n".join(context_parts)
    
    def get_state(self) -> dict:
        """Get the current session state as a dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": str(self.created_at),
            "last_intent": self.last_intent,
            "last_role": self.last_role,
            "last_topic": self.last_topic,
            "last_skills": self.last_skills,
            **self.state
        }
    
    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None


class ConversationMemory:
    """
    Async wrapper around SessionManager for conversation persistence.
    """
    
    def __init__(self):
        # Fallback storage for when DB fails or is misconfigured
        self._memory_fallback: Dict[str, dict] = {}
        # Message fallback
        self._message_fallback: Dict[str, List[dict]] = {}
    
    async def get_session_state(self, session_id: str) -> dict:
        """Get the full session state dictionary from DB with memory fallback."""
        from database.session_manager import session_manager
        try:
            state = await session_manager.get_session_state(session_id)
            if state:
                return state
        except Exception as e:
            logger.error(f"Memory: Failed to get state from DB, using fallback: {e}")
            
        return self._memory_fallback.get(session_id, {})

    async def update_session_state(self, session_id: str, updates: dict) -> None:
        """Update the session state with new values (DB + Memory fallback)."""
        from database.session_manager import session_manager
        
        # 1. Update In-Memory Fallback
        current = self._memory_fallback.get(session_id, {})
        current.update(updates)
        self._memory_fallback[session_id] = current
        
        # 2. Attempt DB synchronization
        try:
            db_current = await session_manager.get_session_state(session_id) or {}
            db_current.update(updates)
            await session_manager.update_session_state(session_id, db_current)
        except Exception as e:
            logger.error(f"Memory: Failed to sync state to DB: {e}")

    async def add_user_message(self, session_id: str, content: str) -> None:
        """Add a user message (DB + Memory fallback)."""
        from database.session_manager import session_manager
        
        # 1. Update In-Memory
        if session_id not in self._message_fallback:
            self._message_fallback[session_id] = []
        self._message_fallback[session_id].append({"role": "user", "content": content, "timestamp": datetime.now()})
        
        # 2. Attempt DB
        try:
            await session_manager.add_message(session_id, "user", content)
        except Exception as e:
            logger.error(f"Memory: Failed to add user message to DB: {e}")

    async def add_assistant_message(
        self,
        session_id: str,
        content: str,
        intent: str = None,
        role: str = None,
        skills: List[str] = None,
        topic: str = None,
        state_updates: dict = None
    ) -> None:
        """Add an assistant message with metadata and update state."""
        from database.session_manager import session_manager
        
        meta = {
            "intent": intent,
            "role": role,
            "skills": skills or [],
            "topic": topic
        }
        await session_manager.add_message(session_id, "assistant", content, meta)
        
        # Update conversation context/state
        if intent or role or topic or skills or state_updates:
            updates = {}
            if intent: updates["last_intent"] = intent
            if role: updates["last_role"] = role
            if topic: updates["last_topic"] = topic
            if skills: updates["last_skills"] = skills
            if state_updates: updates.update(state_updates)
            
            await self.update_session_state(session_id, updates)
    
    async def get_context(self, session_id: str, max_messages: int = 6) -> str:
        """Get conversation context for a session."""
        from database.session_manager import session_manager
        messages = await session_manager.get_messages(session_id, max_messages)
        
        context_parts = []
        for msg in messages:
            role_label = "المستخدم" if msg["role"] == "user" else "المساعد"
            context_parts.append(f"{role_label}: {msg['content'][:200]}")
        
        return "\n".join(context_parts)

# Global memory instance
conversation_memory = ConversationMemory()
