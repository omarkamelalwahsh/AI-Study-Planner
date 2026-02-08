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

class NextAction(BaseModel):
    text: str
    type: str = "follow_up" # follow_up | course_search | catalog_browse | retry | open_question | unknown
    payload: Optional[Dict[str, Any]] = None

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
    CATALOG_BROWSE = "CATALOG_BROWSE"
    CAREER_GUIDANCE = "CAREER_GUIDANCE"
    PROJECT_IDEAS = "PROJECT_IDEAS"  # New: specifically for project suggestions
    GENERAL_QA = "GENERAL_QA"
    FOLLOW_UP = "FOLLOW_UP"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"

class ChatRequest(BaseModel):
    """Incoming chat request from frontend"""
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    language: Optional[str] = "en"

class CourseDetail(BaseModel):
    """Course information returned to frontend"""
    course_id: str
    title: str
    category: Optional[str] = None
    level: Optional[str] = None
    instructor: Optional[str] = None
    duration_hours: Optional[Any] = None
    description: Optional[str] = None     # Support legacy mapping
    description_short: Optional[str] = None
    description_full: Optional[str] = None
    reason: Optional[str] = None
    cover: Optional[str] = None
    fit: Optional[str] = None  # Added for relevance explanation
    linked_skill_keys: List[str] = Field(default_factory=list)
    action: Optional[Action] = None

class ErrorDetail(BaseModel):
    code: str
    message: str

# Legacy support classes kept to satisfy pipeline imports
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
    """A specific skill item"""
    skill_key: str
    label: str
    why: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    courses_count: Optional[int] = None
    course_ids: List[str] = Field(default_factory=list)
    no_courses: bool = False

class SkillGroup(BaseModel):
    """Group of skills for career guidance"""
    skill_area: str
    why_it_matters: str
    skills: List[SkillItem]

class CategoryGroup(BaseModel):
    """Grouped categories"""
    group_title: str
    categories: List[str]

class CategoryDetail(BaseModel):
    """Detailed category for Catalog Browsing"""
    name: str
    why: str
    symbols: Optional[str] = None
    examples: List[str] = Field(default_factory=list)

class CatalogBrowsingData(BaseModel):
    """Structured Catalog Discovery Response"""
    categories: List[CategoryDetail] = Field(default_factory=list)
    next_question: str

class ChoiceQuestion(BaseModel):
    """Multiple-choice question for exploration flow"""
    question: str
    choices: List[str] = Field(default_factory=list)

class QuizCollected(BaseModel):
    goal_type: Optional[str] = None
    track: Optional[str] = None
    level: Optional[str] = None
    weekly_time: Optional[str] = None
    learning_style: Optional[str] = None

class QuizData(BaseModel):
    is_active: bool = False
    question: Optional[str] = None
    choices: List[str] = Field(default_factory=list)
    collected: QuizCollected = Field(default_factory=QuizCollected)

class LearningItem(BaseModel):
    """Represents a day or week in a schedule"""
    day: str
    topics: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)
    deliverable: Optional[str] = None

class LearningPlan(BaseModel):
    """Structured learning plan"""
    topic: Optional[str] = None
    duration: Optional[str] = None
    time_per_day: Optional[str] = None
    schedule: List[LearningItem] = Field(default_factory=list)

class ProjectDetail(BaseModel):
    """Project suggestion"""
    title: str
    level: str = "Beginner"
    features: List[str] = Field(default_factory=list)
    stack: List[str] = Field(default_factory=list)
    deliverable: Optional[str] = None

class FlowStateUpdates(BaseModel):
    """Session state updates"""
    model_config = {"extra": "allow"}
    topic: Optional[str] = None
    track: Optional[str] = None
    duration: Optional[str] = None
    time_per_day: Optional[str] = None
    active_flow: Optional[str] = None

class RouterOutput(BaseModel):
    """Output from the LLM Router"""
    intent: str  # Kept as string to allow flexibility, mapped to IntentType later
    topic: Optional[str] = None
    needs_courses: bool = False
    needs_plan: bool = False
    needs_projects: bool = False
    one_question: Optional[OneQuestion] = None

class IntentResult(BaseModel):
    """Legacy Intent Result (kept for compatibility during migration)"""
    intent: IntentType
    confidence: float = 0.0
    topic: Optional[str] = None
    sub_topic: Optional[str] = None
    role: Optional[str] = None
    level: Optional[str] = None
    specific_course: Optional[str] = None
    needs_courses: bool = False
    needs_explanation: bool = False
    needs_one_question: bool = False # Legacy flag, superseded by router output
    slots: dict = Field(default_factory=dict)

class SemanticResult(BaseModel):
    """Result from semantic understanding"""
    primary_domain: Optional[str] = None
    secondary_domains: List[str] = Field(default_factory=list)
    extracted_skills: List[str] = Field(default_factory=list)
    user_level: Optional[str] = None
    brief_explanation: Optional[str] = None
    is_in_catalog: bool = True
    focus_area: Optional[str] = None
    tool: Optional[str] = None
    search_axes: List[str] = Field(default_factory=list)

class SkillValidationResult(BaseModel):
    """Result from skill extraction"""
    validated_skills: List[str] = Field(default_factory=list)
    skill_to_domain: Dict[str, str] = Field(default_factory=dict)
    unmatched_terms: List[str] = Field(default_factory=list)

class CVSkillCategory(BaseModel):
    name: str
    confidence: float

class CVSkills(BaseModel):
    strong: List[CVSkillCategory] = Field(default_factory=list)
    weak: List[CVSkillCategory] = Field(default_factory=list)
    missing: List[CVSkillCategory] = Field(default_factory=list)

class RadarItem(BaseModel):
    area: str
    value: int

class CVDashboard(BaseModel):
    """CV Analysis Dashboard"""
    candidate: dict = Field(default_factory=dict)
    score: dict = Field(default_factory=dict)
    roleFit: dict = Field(default_factory=dict)
    skills: CVSkills = Field(default_factory=CVSkills)
    radar: List[RadarItem] = Field(default_factory=list)

class ChatResponse(BaseModel):
    """The unified, stable response schema for the Career Copilot."""
    intent: IntentType
    answer: str = Field(..., description="The textual response to the user.")
    courses: List[CourseDetail] = Field(default_factory=list, description="List of recommended courses.")
    projects: List[ProjectDetail] = Field(default_factory=list, description="List of suggested project ideas.")
    categories: List[str] = Field(default_factory=list, description="Relevant catalog categories.")
    next_actions: List[NextAction] = Field(default_factory=list, description="Suggested next steps or buttons.")
    session_state: Dict[str, Any] = Field(default_factory=dict, description="Metadata and session-specific state.")
    
    # Optional fields for internal tracking / UI components
    success: bool = True
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
