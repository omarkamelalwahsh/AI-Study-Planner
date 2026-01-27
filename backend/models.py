"""
Career Copilot RAG Backend - Pydantic Models
Request/Response schemas for the API.
"""
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class IntentType(str, Enum):
    COURSE_SEARCH = "COURSE_SEARCH"
    CAREER_GUIDANCE = "CAREER_GUIDANCE"
    CATALOG_BROWSING = "CATALOG_BROWSING"
    PROJECT_IDEAS = "PROJECT_IDEAS"
    COURSE_DETAILS = "COURSE_DETAILS"
    LEARNING_PATH = "LEARNING_PATH"
    FOLLOW_UP = "FOLLOW_UP"
    CONCEPT_EXPLAIN = "CONCEPT_EXPLAIN"
    AMBIGUOUS = "AMBIGUOUS"


class ChatRequest(BaseModel):
    """Incoming chat request from frontend"""
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None


class CourseDetail(BaseModel):
    """Course information returned to frontend"""
    course_id: str
    title: str
    category: Optional[str] = None
    level: Optional[str] = None
    instructor: Optional[str] = None
    duration_hours: Optional[Any] = None  # Float or string "Unknown"
    description: Optional[str] = None     # Legacy field, mapped to description_full
    description_short: Optional[str] = None
    description_full: Optional[str] = None
    reason: Optional[str] = None
    cover: Optional[str] = None


class ProjectDetail(BaseModel):
    """Project suggestion for career guidance"""
    title: str
    difficulty: str = "Beginner"  # Renamed from level to difficulty per V4 spec
    description: str
    deliverables: List[str] = []
    suggested_tools: List[str] = []
    
    # Legacy support if needed
    level: Optional[str] = None 
    skills: List[str] = []


class SkillGroup(BaseModel):
    """Group of skills for career guidance"""
    skill_area: str
    why_it_matters: str
    skills: List[str]


class WeeklySchedule(BaseModel):
    """One week in a learning plan"""
    week: int
    focus: str
    courses: List[str] = []  # Course IDs
    outcomes: List[str] = []


class LearningPlan(BaseModel):
    """Structured learning plan"""
    weeks: Optional[int] = None
    hours_per_day: Optional[float] = None
    schedule: List[WeeklySchedule] = []


class ErrorDetail(BaseModel):
    """Error information"""
    code: str
    message: str


class ChatResponse(BaseModel):
    """Response sent back to frontend"""
    session_id: str
    intent: str
    answer: str
    courses: List[CourseDetail] = []
    projects: List[ProjectDetail] = []
    skill_groups: List[SkillGroup] = []
    learning_plan: Optional[LearningPlan] = None
    error: Optional[ErrorDetail] = None
    request_id: str


class IntentResult(BaseModel):
    """Result from intent classification"""
    intent: IntentType
    role: Optional[str] = None
    level: Optional[str] = None
    specific_course: Optional[str] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


class SemanticResult(BaseModel):
    """Result from semantic understanding"""
    primary_domain: Optional[str] = None
    secondary_domains: List[str] = []
    extracted_skills: List[str] = []
    user_level: Optional[str] = None  # Beginner, Intermediate, Advanced
    preferences: dict = {}


class SkillValidationResult(BaseModel):
    """Result from skill extraction and validation"""
    validated_skills: List[str] = []
    skill_to_domain: dict = {}
    unmatched_terms: List[str] = []
