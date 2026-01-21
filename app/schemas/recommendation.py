from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict

Language = Literal["ar", "en", "mixed", "other"]
Level = Literal["Beginner", "Intermediate", "Advanced"]
Readiness = Literal["Ready", "Missing", "Unknown"]

class CourseOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Accept "id" from LLM or internal data, map to "course_id"
    course_id: str = Field(alias="id")
    title: str
    category: Optional[str] = None # Keeping optional to avoid crashes if missing, though strict schema implies required.
    level: Level
    duration_hours: float = 0
    instructor: str
    prerequisites: List[str] = Field(default_factory=list)
    readiness: Readiness = "Unknown"
    missing_skills: List[str] = Field(default_factory=list)
    reason: str
    score: Optional[float] = 0.0

class StudyPlanWeek(BaseModel):
    week: int
    focus: str
    tasks: List[str]
    milestone: str

class LLMRecommendationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    language: Language = "mixed"
    intent: str
    assistant_message: str
    follow_up_question: Optional[str] = None
    consent_needed: bool = False
    courses: List[CourseOut] = Field(default_factory=list)
    study_plan: List[StudyPlanWeek] = Field(default_factory=list)
    notes: Dict[str, Optional[str]] = Field(default_factory=dict)
