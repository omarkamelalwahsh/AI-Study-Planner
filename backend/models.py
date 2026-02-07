"""
Career Copilot RAG Backend - Pydantic Models
Request/Response schemas for the API.
"""
from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, Field
from enum import Enum


class Card(BaseModel):
    type: str  # roadmap | skills | courses | assessment | cv_summary | next_steps | notes
    heading: str
    bullets: List[str]

class RadarItem(BaseModel):
    area: str
    value: int

class Action(BaseModel):
    type: str = "OPEN_COURSE_DETAILS"
    course_id: str

class OneQuestion(BaseModel):
    question: str
    choices: List[str]

class IntentType(str, Enum):
    COURSE_SEARCH = "COURSE_SEARCH"
    CAREER_GUIDANCE = "CAREER_GUIDANCE"
    CATALOG_BROWSING = "CATALOG_BROWSING"
    LEARNING_PATH = "LEARNING_PATH"
    FOLLOW_UP = "FOLLOW_UP"
    GENERAL_QA = "GENERAL_QA"
    SAFE_FALLBACK = "SAFE_FALLBACK"
    EXPLORATION = "EXPLORATION"
    EXPLORATION_FOLLOWUP = "EXPLORATION_FOLLOWUP"
    CV_ANALYSIS = "CV_ANALYSIS" # Internal use for uploads
    PROJECT_IDEAS = "PROJECT_IDEAS" # Internal mapping for projects
    COURSE_DETAILS = "COURSE_DETAILS" # Added for Honesty Guard
    TRACK_START = "TRACK_START"


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
    linked_skill_keys: List[str] = Field(default_factory=list) # V12 Popover Mapping
    action: Optional[Action] = None # Strict UI Action


# Legacy support classes kept but decoupled from main response models
class WeeklySchedule(BaseModel):
    """Legacy weekly schedule"""
    week: int
    focus: str
    courses: List[str] = Field(default_factory=list)
    outcomes: List[str] = Field(default_factory=list)

class LearningPhase(BaseModel):
    """Legacy learning phase"""
    title: str
    weeks: str
    skills: List[str] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)

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
    duration: Optional[str] = None
    daily_time: Optional[str] = None


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
    radar: List[RadarItem] = Field(default_factory=list) # [{area, value}]
    projects: List[dict] = Field(default_factory=list) # [{title, level, description, skills}]
    atsChecklist: List[dict] = Field(default_factory=list) # [{id, text, done}]
    notes: dict = Field(default_factory=dict) # {strengths, gaps}
    recommendations: List[str] = Field(default_factory=list) # Legacy fallback

class ErrorDetail(BaseModel):
    code: str
    message: str

# --- V1.2/V1.3 New Models ---
class ChoiceQuestion(BaseModel):
    """Multiple-choice question for exploration flow"""
    question: str
    choices: List[str] = Field(default_factory=list)


class LearningItem(BaseModel):
    """Represents a day or week in a schedule"""
    day_or_week: str = Field(alias="day") # Support both for internal safety
    topics: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    deliverable: Optional[str] = None

    class Config:
        populate_by_name = True


class LearningPlan(BaseModel):
    """Structured learning plan (Production V1)"""
    topic: Optional[str] = None
    duration: Optional[str] = None
    time_per_day: Optional[str] = None
    schedule: List[LearningItem] = Field(default_factory=list)


class ProjectDetail(BaseModel):
    """Project suggestion for career guidance"""
    title: str
    level: str = "Beginner"
    features: List[str] = Field(default_factory=list)
    stack: List[str] = Field(default_factory=list)
    deliverable: Optional[str] = None
    # Legacy fields
    description: Optional[str] = None
    suggested_tools: List[str] = Field(default_factory=list)


class FlowStateUpdates(BaseModel):
    """Session state updates for the frontend"""
    model_config = {"extra": "allow"}
    
    topic: Optional[str] = None
    track: Optional[str] = None
    duration: Optional[str] = None
    time_per_day: Optional[str] = None
    active_flow: Optional[str] = None
    exploration: Optional[dict] = None


class ChatResponse(BaseModel):
    """Strict JSON Output Contract for Career Copilot (New Schema)"""
    intent: str
    language: str
    title: str
    answer: str
    cards: List[Card] = Field(default_factory=list)
    radar: List[RadarItem] = Field(default_factory=list) # Top-level radar for CV Analysis
    courses: List[CourseDetail] = Field(default_factory=list)
    one_question: Optional[OneQuestion] = None
    
    # Metadata and State tracking (Internal/Backend use)
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    flow_state_updates: Optional[FlowStateUpdates] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    # Legacy/Extended fields (kept for backward compatibility during transition)
    learning_plan: Optional[LearningPlan] = None
    projects: List[ProjectDetail] = Field(default_factory=list)
    all_relevant_courses: List[CourseDetail] = Field(default_factory=list)
    skill_groups: List[SkillGroup] = Field(default_factory=list)
    catalog_browsing: Optional[CatalogBrowsingData] = None
    dashboard: Optional[CVDashboard] = None
    error: Optional[ErrorDetail] = None

 
