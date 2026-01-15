from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime

class UserConstraints(BaseModel):
    weekly_hours: int = 6
    timeframe_weeks: int = 8
    preferred_language: str = "ar"
    level: str = "beginner"
    other: Optional[str] = None

class UserProfile(BaseModel):
    current_role: Optional[str] = None
    skills: List[str] = []
    experience_years: float = 0

class UserIntent(BaseModel):
    query: str
    career_goal: Optional[str] = None
    sector: Optional[str] = None
    constraints: Dict[str, Any] = {}
    language: str = "en"  # ar | en | mixed
    confidence_level: str = "clear"  # clear | vague
    is_career_related: bool = True

class CareerCopilotRequest(BaseModel):
    session_id: Optional[UUID] = None
    new_session: bool = False
    message: str
    use_memory: bool = True
    save_memory: str = "ask"  # ask | never | always
    export_pdf: bool = False
    constraints: UserConstraints = Field(default_factory=UserConstraints)
    user_profile: UserProfile = Field(default_factory=UserProfile)

class RecommendedCourseSchema(BaseModel):
    course_id: str
    title: str
    instructor: Optional[str] = None
    duration_hours: Optional[float] = None
    level: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    why: str

class PlanItemSchema(BaseModel):
    course_id: str
    title: str
    order: int

class PlanWeekSchema(BaseModel):
    week_number: int
    items: List[PlanItemSchema]

class Playlist(BaseModel):
    status: str  # available | partial | not_available
    course_ids: List[str]

class Citation(BaseModel):
    source_type: str  # role_kb | course_catalog
    id: str
    content: Optional[str] = None

class PDFInfo(BaseModel):
    pdf_id: Optional[str] = None
    pdf_url: Optional[str] = None

class PlanOutput(BaseModel):
    session_id: UUID
    plan_id: Optional[UUID] = None
    output_language: str
    plan_type: str  # our_courses | hybrid | custom
    coverage_score: float
    summary: str
    required_skills: List[str]
    recommended_courses: List[RecommendedCourseSchema]
    plan_weeks: List[PlanWeekSchema]
    playlist: Playlist
    citations: List[Citation]
    confidence: str  # low | medium | high
    follow_up_questions: List[str]
    pdf: Optional[PDFInfo] = None

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
