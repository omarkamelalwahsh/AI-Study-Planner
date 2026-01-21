import logging
import math
from typing import List, Dict, Any
from app.schemas_career import PlanWeekSchema, PlanItemSchema, RecommendedCourseSchema

logger = logging.getLogger(__name__)

class StudyPlanner:
    @staticmethod
    def generate_plan(required_skills: List[str], recommended_courses: List[RecommendedCourseSchema], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        STEP 5 — DECISION POLICY
        Based on coverage percentage.
        70%+ -> OUR COURSES PLAN
        30-70% -> HYBRID PLAN
        <30% -> CUSTOM PLAN
        """
        # Calculate coverage: simple ratio for now
        # In production, we'd map courses to skills exactly
        num_required = len(required_skills)
        num_covered = min(num_required, len(recommended_courses))
        coverage_score = num_covered / num_required if num_required > 0 else 0.0
        
        if coverage_score >= 0.70:
            plan_type = "our_courses"
        elif coverage_score >= 0.30:
            plan_type = "hybrid"
        else:
            plan_type = "custom"
            
        weekly_hours = constraints.get("weekly_hours", 6)
        weeks_count = constraints.get("timeframe_weeks", 8)
        
        plan_weeks = []
        current_course_idx = 0
        
        for w in range(1, weeks_count + 1):
            week_items = []
            hours_filled = 0
            
            while current_course_idx < len(recommended_courses) and hours_filled < weekly_hours:
                course = recommended_courses[current_course_idx]
                dur = course.duration_hours or 5.0
                
                week_items.append(PlanItemSchema(
                    course_id=course.course_id,
                    title=course.title,
                    order=len(week_items) + 1
                ))
                
                hours_filled += dur
                current_course_idx += 1
                
            plan_weeks.append(PlanWeekSchema(
                week_number=w,
                items=week_items
            ))
            
        return {
            "plan_type": plan_type,
            "coverage_score": coverage_score,
            "plan_weeks": plan_weeks
        }
