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
    In-memory conversation storage.
    In production, this would use Redis or a database.
    """
    
    def __init__(self, max_sessions: int = 1000):
        self._conversations: Dict[str, Conversation] = {}
        self._max_sessions = max_sessions
    
    def get_or_create(self, session_id: str) -> Conversation:
        """Get existing conversation or create new one."""
        if session_id not in self._conversations:
            self._conversations[session_id] = Conversation(session_id=session_id)
            self._cleanup_if_needed()
        return self._conversations[session_id]
    
    def get(self, session_id: str) -> Optional[Conversation]:
        """Get conversation by session ID."""
        return self._conversations.get(session_id)
    
    def add_user_message(self, session_id: str, content: str) -> Conversation:
        """Add a user message to the conversation."""
        conv = self.get_or_create(session_id)
        conv.add_message("user", content)
        return conv
    
    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        intent: str = None,
        role: str = None,
        skills: List[str] = None,
        topic: str = None,
        state_updates: dict = None
    ) -> Conversation:
        """Add an assistant message with metadata."""
        conv = self.get_or_create(session_id)
        conv.add_message("assistant", content, {
            "intent": intent,
            "role": role,
            "skills": skills or [],
            "topic": topic
        })
        
        # Update conversation context
        if intent:
            conv.last_intent = intent
        if role:
            conv.last_role = role
        if topic:
            conv.last_topic = topic
        if skills:
            conv.last_skills = skills
        if state_updates:
            conv.state.update(state_updates)
        
        return conv
    
    def get_context(self, session_id: str) -> str:
        """Get conversation context for a session."""
        conv = self.get(session_id)
        if conv:
            return conv.get_context()
        return ""
        
    def get_session_state(self, session_id: str) -> dict:
        """Get the full session state dictionary."""
        conv = self.get(session_id)
        if conv:
            return conv.get_state()
        return {}

    def update_session_state(self, session_id: str, updates: dict) -> None:
        """Update the session state with new values."""
        conv = self.get_or_create(session_id)
        conv.state.update(updates)
    
    def _cleanup_if_needed(self):
        """Remove oldest sessions if we exceed max."""
        if len(self._conversations) > self._max_sessions:
            # Sort by creation time and remove oldest
            sorted_sessions = sorted(
                self._conversations.items(),
                key=lambda x: x[1].created_at
            )
            to_remove = len(self._conversations) - self._max_sessions
            for session_id, _ in sorted_sessions[:to_remove]:
                del self._conversations[session_id]
            logger.info(f"Cleaned up {to_remove} old sessions")


# Global memory instance
conversation_memory = ConversationMemory()
