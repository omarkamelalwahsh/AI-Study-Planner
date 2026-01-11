from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any

class Recommendation(BaseModel):
    title: str
    url: str
    category: Optional[str] = "General"
    level: Optional[str] = "All Levels"
    rank: int = Field(..., ge=1, le=10)
    score: float
    matched_keywords: List[str] = []
    why: List[str] = []
    debug_info: Optional[Dict[str, Any]] = None

class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User search query")
    top_k: int = Field(30, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    enable_reranking: bool = False

    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty strings')
        return v

class RecommendResponse(BaseModel):
    results: List[Recommendation]
    total_found: int
    debug_info: Dict[str, Any]

class UserProfile(BaseModel):
    topic: str = Field(..., min_length=1)
    level: str = Field(..., pattern="^(Beginner|Intermediate|Advanced)$")
    goal: str = Field(..., pattern="^(Get a job|Build projects|Improve in current work|Pass an exam|Learn basics)$")
    hours_per_day: float = Field(..., ge=0.5, le=6.0)
    days_per_week: int = Field(..., ge=1, le=7)
    plan_duration_weeks: int = Field(..., gt=0, le=52)
    preferred_content: Optional[str] = "Mixed"
    budget: Optional[str] = "Any"

    @validator("plan_duration_weeks")
    def validate_weeks(cls, v):
        if v not in {2, 4, 8, 12}:
            raise ValueError("Plan duration must be one of: 2, 4, 8, 12 weeks")
        return v

class WeeklyPlan(BaseModel):
    week_title: str
    topics: List[str]
    courses: List[str]
    estimated_hours: float
    mini_tasks: List[str]

class LearningPlan(BaseModel):
    recommended_courses: List[Recommendation]
    weekly_schedule: List[WeeklyPlan]
    capstone_project: str
    checklist: List[str]
    tips: List[str]
