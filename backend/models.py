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
    CV_ANALYSIS = "CV_ANALYSIS"
    ATS_CHECK = "ATS_CHECK"
    AMBIGUOUS = "AMBIGUOUS"
    ERROR = "ERROR"
    GENERAL_QA = "GENERAL_QA"
    SAFE_FALLBACK = "SAFE_FALLBACK"


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
    fit: Optional[str] = None
    why_recommended: Optional[str] = None
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


class SkillItem(BaseModel):
    """A specific skill with justification"""
    name: str
    why: Optional[str] = None
    courses_count: Optional[int] = None
    course_ids: List[str] = [] # V10 Grounding

class SkillGroup(BaseModel):
    """Group of skills for career guidance"""
    skill_area: str
    why_it_matters: str
    skills: List[SkillItem]


class WeeklySchedule(BaseModel):
    """One week in a learning plan (Legacy)"""
    week: int
    focus: str
    courses: List[str] = []
    outcomes: List[str] = []

class LearningPhase(BaseModel):
    """A phase in a learning path (New V6)"""
    title: str
    weeks: str  # e.g. "1-3"
    skills: List[str] = []
    deliverables: List[str] = []

class LearningPlan(BaseModel):
    """Structured learning plan"""
    weeks: Optional[int] = None
    hours_per_day: Optional[float] = None
    schedule: List[WeeklySchedule] = []
    phases: List[LearningPhase] = [] # V6 Support




class IntentResult(BaseModel):
    """Result from intent classification"""
    intent: IntentType
    role: Optional[str] = None
    level: Optional[str] = None
    specific_course: Optional[str] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    confidence: float = 0.0
    slots: dict = {}
    # V5 Hybrid Policy Flags
    needs_explanation: bool = False
    needs_courses: bool = False
    search_axes: List[str] = [] # Added for V5 Relevance Gate


class SemanticResult(BaseModel):
    """Result from semantic understanding"""
    primary_domain: Optional[str] = None
    secondary_domains: List[str] = []
    extracted_skills: List[str] = []
    user_level: Optional[str] = None  # Beginner, Intermediate, Advanced
    preferences: dict = {}
    # V5 New Fields
    brief_explanation: Optional[str] = None
    search_axes: List[str] = []
    # V6 Compound Query Support
    focus_area: Optional[str] = None # The "What" (e.g. Database)
    tool: Optional[str] = None       # The "How" (e.g. Python)


class SkillValidationResult(BaseModel):
    """Result from skill extraction and validation"""
    validated_skills: List[str] = []
    skill_to_domain: dict = {}
    unmatched_terms: List[str] = []

class CVSkillCategory(BaseModel):
    name: str
    confidence: float

class CVSkills(BaseModel):
    strong: List[CVSkillCategory] = []
    weak: List[CVSkillCategory] = []
    missing: List[CVSkillCategory] = []

class CVDashboard(BaseModel):
    """Structured CV Analysis Dashboard (Rich UI Schema)"""
    candidate: dict = {} # {name, targetRole, seniority}
    score: dict = {} # {overall, skills, experience, projects, marketReadiness}
    roleFit: dict = {} # {detectedRoles, direction, summary}
    skills: CVSkills = CVSkills()
    radar: List[dict] = [] # [{area, value}]
    projects: List[dict] = [] # [{title, level, description, skills}]
    atsChecklist: List[dict] = [] # [{id, text, done}]
    notes: dict = {} # {strengths, gaps}
    recommendations: List[str] = [] # Legacy fallback

class ErrorDetail(BaseModel):
    code: str
    message: str

class ChatResponse(BaseModel):
    """Response returned to frontend"""
    session_id: str
    intent: IntentType
    answer: str
    courses: List[CourseDetail] = [] # Top 3 (recommended_courses)
    all_relevant_courses: List[CourseDetail] = [] # Full list
    projects: List[ProjectDetail] = []
    skill_groups: List[SkillGroup] = []
    learning_plan: Optional[LearningPlan] = None
    dashboard: Optional[CVDashboard] = None
    error: Optional[ErrorDetail] = None
    request_id: Optional[str] = None
