from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Dict, Any, Union
from datetime import datetime

Role = Literal["system", "user", "assistant"]

class MessageBase(BaseModel):
    content: str
    language: Optional[str] = None

class MessageCreate(MessageBase):
    pass

class ChatMsg(BaseModel):
    role: Role
    content: str = Field(min_length=1)

class ChatMessage(MessageBase):
    id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class SessionBase(BaseModel):
    title: str = "Chat"
    language: str = "en"

class SessionCreate(SessionBase):
    pass

class ChatSession(SessionBase):
    id: str
    state: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None
    messages: Optional[List[ChatMsg]] = None

    # Optional meta
    consent_to_show_full_list: Optional[bool] = None
    hours_per_week: Optional[int] = Field(default=None, ge=1, le=60)
    weeks: Optional[int] = Field(default=None, ge=1, le=52)
    user_profile: Optional[Dict[str, Any]] = None
    client_state: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def ensure_one_of_message_or_messages(self):
        if not self.message and not self.messages:
            raise ValueError("Either 'message' or 'messages' is required.")
        return self

    def normalized_messages(self) -> List[ChatMsg]:
        if self.messages:
            return self.messages
        return [ChatMsg(role="user", content=self.message or "")]
