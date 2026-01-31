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
    EXPLORATION = "EXPLORATION"  # V18: User doesn't know what to learn


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
    linked_skill_keys: List[str] = [] # V12 Popover Mapping


class ProjectDetail(BaseModel):
    """Project suggestion for career guidance"""
    title: str
    difficulty: str = "Beginner"  # Renamed from level to difficulty per V4 spec
    description: str
    deliverables: List[str] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)
    
    # Legacy support if needed
    level: Optional[str] = None 
    skills: List[str] = Field(default_factory=list)


class SkillItem(BaseModel):
    """A specific skill with justification and catalog grounding"""
    skill_key: str  # Canonical name
    label: str      # Display label
    why: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    courses_count: Optional[int] = None
    course_ids: List[str] = Field(default_factory=list) # Mapping to course IDs
    no_courses: bool = False

class SkillGroup(BaseModel):
    """Group of skills for career guidance"""
    skill_area: str
    why_it_matters: str
    skills: List[SkillItem]


class WeeklySchedule(BaseModel):
    """One week in a learning plan (Legacy)"""
    week: int
    focus: str
    courses: List[str] = Field(default_factory=list)
    outcomes: List[str] = Field(default_factory=list)

class LearningPhase(BaseModel):
    """A phase in a learning path (New V6)"""
    title: str
    weeks: str  # e.g. "1-3"
    skills: List[str] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)

class LearningPlan(BaseModel):
    """Structured learning plan (V6 Standard)"""
    weeks: Optional[int] = None
    hours_per_day: Optional[float] = None
    phases: List[LearningPhase] = Field(default_factory=list)
    # schedule: List[WeeklySchedule] = [] # Removed duplicate/confusing field




class IntentResult(BaseModel):
    """Result from intent classification"""
    intent: IntentType
    role: Optional[str] = None
    level: Optional[str] = None
    specific_course: Optional[str] = None
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    confidence: float = 0.0
    slots: dict = Field(default_factory=dict)
    # V5 Hybrid Policy Flags
    needs_explanation: bool = False
    needs_courses: bool = False
    search_axes: List[str] = Field(default_factory=list) # Added for V5 Relevance Gate
    topic: Optional[str] = None  # V12 Core topic detected
    primary_domain: Optional[str] = None # Added for V3 Canonicalization


class SemanticResult(BaseModel):
    """Result from semantic understanding"""
    primary_domain: Optional[str] = None
    secondary_domains: List[str] = Field(default_factory=list)
    extracted_skills: List[str] = Field(default_factory=list)
    user_level: Optional[str] = None  # Beginner, Intermediate, Advanced
    preferences: dict = Field(default_factory=dict)
    # V5 New Fields
    brief_explanation: Optional[str] = None
    search_axes: List[str] = Field(default_factory=list)
    # V12 Multi-Axis Support
    axes: List[dict] = Field(default_factory=list) # List of {"name": "...", "categories": [...]}
    is_in_catalog: bool = True
    missing_domain: Optional[str] = None
    # V6 Compound Query Support
    focus_area: Optional[str] = None # The "What" (e.g. Database)
    tool: Optional[str] = None       # The "How" (e.g. Python)
    semantic_lock: bool = False      # Added for V3 Stop Drift


class SkillValidationResult(BaseModel):
    """Result from skill extraction and validation"""
    validated_skills: List[str] = Field(default_factory=list)
    skill_to_domain: dict = Field(default_factory=dict)
    unmatched_terms: List[str] = Field(default_factory=list)

class CVSkillCategory(BaseModel):
    name: str
    confidence: float

class CVSkills(BaseModel):
    strong: List[CVSkillCategory] = Field(default_factory=list)
    weak: List[CVSkillCategory] = Field(default_factory=list)
    missing: List[CVSkillCategory] = Field(default_factory=list)

class CategoryGroup(BaseModel):
    """Legacy Grouped categories"""
    group_title: str
    categories: List[str]

class CategoryDetail(BaseModel):
    """Detailed category for Catalog Browsing"""
    name: str
    why: str
    symbols: Optional[str] = None # Added for V3 Visual Polish
    examples: List[str] = Field(default_factory=list)

class CatalogBrowsingData(BaseModel):
    """Structured Catalog Discovery Response"""
    categories: List[CategoryDetail] = Field(default_factory=list)
    next_question: str

class CVDashboard(BaseModel):
    """Structured CV Analysis Dashboard (Rich UI Schema)"""
    candidate: dict = Field(default_factory=dict) # {name, targetRole, seniority}
    score: dict = Field(default_factory=dict) # {overall, skills, experience, projects, marketReadiness}
    roleFit: dict = Field(default_factory=dict) # {detectedRoles, direction, summary}
    skills: CVSkills = Field(default_factory=CVSkills)
    radar: List[dict] = Field(default_factory=list) # [{area, value}]
    projects: List[dict] = Field(default_factory=list) # [{title, level, description, skills}]
    atsChecklist: List[dict] = Field(default_factory=list) # [{id, text, done}]
    notes: dict = Field(default_factory=dict) # {strengths, gaps}
    recommendations: List[str] = Field(default_factory=list) # Legacy fallback

class ErrorDetail(BaseModel):
    code: str
    message: str

class ChatResponse(BaseModel):
    """Response returned to frontend"""
    session_id: str
    intent: IntentType
    mode: Optional[str] = None # e.g. "category_explorer"
    answer: str
    confidence: float = 0.0
    topic: Optional[str] = None
    role: Optional[str] = None
    courses: List[CourseDetail] = Field(default_factory=list) 
    all_relevant_courses: List[CourseDetail] = Field(default_factory=list) 
    projects: List[ProjectDetail] = Field(default_factory=list)
    skill_groups: List[SkillGroup] = Field(default_factory=list)
    catalog_browsing: Optional[CatalogBrowsingData] = None
    learning_plan: Optional[LearningPlan] = None
    dashboard: Optional[CVDashboard] = None
    error: Optional[ErrorDetail] = None
    request_id: Optional[str] = None
    followup_question: Optional[str] = None 
