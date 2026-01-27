"""
Career Copilot RAG Backend - Step 6: Response Builder
Dynamic response generation based on intent type.
"""
import logging
from typing import List, Optional, Dict

from llm.base import LLMBase
from models import (
    IntentType, IntentResult, CourseDetail, ProjectDetail, 
    SkillValidationResult, SkillGroup, LearningPlan, WeeklySchedule
)

logger = logging.getLogger(__name__)


RESPONSE_SYSTEM_PROMPT = """You are "Career Copilot": a production-grade RAG career assistant.
You MUST be data-grounded: never invent courses, categories, instructors, durations, or IDs.
If data is missing, say "غير متوفر في الكتالوج" and continue safely.

========================================================
1) Core Principles (Non-Negotiable)
========================================================
A) Data Grounding:
- Use ONLY provided catalog_results.
- Never fabricate.
- If user asks for something not in catalog: say not found, then offer nearest in-catalog options.

B) Strict Intent Separation (NO MIXING):
- Your response MUST represent exactly ONE intent.
- Do not mix concept explanations with courses unless explicit.
- Do not inject career guidance into a course search unless intent == CAREER_GUIDANCE.

========================================================
2) Response Requirements Per Intent
========================================================
A) CONCEPT_EXPLAIN:
- Explain simply in user's language.
- No courses.
- End with optional question: "تحب أرشح كورسات من الكتالوج ولا كان قصدك شرح وبس؟"

B) COURSE_SEARCH:
- Return list of matched courses (sorted by relevance).
- Ask ONE follow-up if needed.

C) COURSE_DETAILS:
- Return single course full details.

D) CATALOG_BROWSING:
- Show categories and counts.
- Ask: "تحب أنهي مجال؟"

E) CAREER_GUIDANCE:
Output sections:
1) Short guidance (bullet points).
2) Skill areas (3-6) (mapped to skill_groups).
3) Courses (5-10) strictly relevant.
4) Projects: 3 ideas (Beginner/Intermediate/Advanced).
5) Ask: "تحب أعملك خطة؟ كام ساعة في اليوم؟"

F) PROJECT_IDEAS:
- Provide 3 projects only (Beginner/Intermediate/Advanced).
- No courses unless requested.

G) LEARNING_PATH:
- Build a weekly plan using ONLY retrieved courses.
- Include weekly breakdown + which courses + outcomes.

========================================================
3) Output Schema (Strict JSON)
========================================================
Return ONLY valid JSON.

{
  "intent": "...",
  "answer": "short human-readable summary",
  "clarifying_question": null | "string",
  "skill_groups": [
     {
       "skill_area": "string",
       "why_it_matters": "string",
       "skills": ["string", "..."]
     }
  ],
  "courses": [
    {
      "course_id": "string",
      "title": "string",
      "level": "Beginner|Intermediate|Advanced",
      "category": "string",
      "instructor": "string",
      "duration_hours": 0,
      "cover": "string|null",
      "reason": "string",
      "description_short": "string (truncated max 220 chars)",
      "description_full": "string"
    }
  ],
  "projects": [
    {
      "title": "string",
      "difficulty": "Beginner|Intermediate|Advanced",
      "description": "string",
      "deliverables": ["string", "..."],
      "suggested_tools": ["string", "..."]
    }
  ],
  "learning_plan": {
     "weeks": 0,
     "hours_per_day": 0,
     "schedule": [
        {
          "week": 1,
          "focus": "string",
          "courses": ["course_id", "..."],
          "outcomes": ["string", "..."]
        }
     ]
  }
}
"""


class ResponseBuilder:
    """
    Step 6: Build dynamic response based on intent.
    """
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def build(
        self,
        intent_result: IntentResult,
        courses: List[CourseDetail],
        skill_result: SkillValidationResult,
        user_message: str,
        context: Optional[dict] = None,
    ) -> tuple[str, List[ProjectDetail], List[CourseDetail], List[SkillGroup], Optional[LearningPlan]]:
        """
        Build the response text using the production V4 system prompt.
        """
        # Apply strict k_return rule (V4 strictness)
        num_courses = len(courses)
        if num_courses >= 3:
            k_return = max(min(8, num_courses), 3)
            courses_context = courses[:k_return]
        else:
            courses_context = courses

        # Prepare context for the LLM
        courses_data = [
            {
                "course_id": c.course_id,
                "title": c.title,
                "level": c.level,
                "category": c.category,
                "instructor": c.instructor,
                "duration_hours": c.duration_hours,
                "description": c.description,
            }
            for c in courses_context
        ]
        
        skills_data = {
            "validated": skill_result.validated_skills,
            "unmatched": skill_result.unmatched_terms,
            "skill_to_domain": skill_result.skill_to_domain
        }
        
        # Build Session State string
        session_state = {}
        if context:
            session_state = {
                "last_intent": context.get("last_intent"),
                "last_topic": context.get("last_topic"),
                "last_domain": context.get("last_domain"),
                "last_results_course_ids": context.get("last_results_course_ids", []),
                "last_plan_constraints": context.get("last_plan_constraints"),
                "pagination_offset": context.get("pagination_offset", 0)
            }

        prompt = f"""User Message: "{user_message}"
Intent identified: {intent_result.intent.value}
Target Role: {intent_result.role}

RETRIEVED DATA (Only use this):
catalog_results: {courses_data}
skills_catalog: {skills_data}
session_state: {session_state}

Generate the structured response in JSON format according to the rules."""

        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                temperature=0.3
            )
            
            # 1. Answer & Clarification
            answer = response.get("answer", "")
            if response.get("clarifying_question"):
                answer = f"{answer}\n\n{response['clarifying_question']}"
                
            # 2. Skill Groups
            skill_groups = []
            for sg in response.get("skill_groups", []):
                skill_groups.append(SkillGroup(
                    skill_area=sg.get("skill_area", ""),
                    why_it_matters=sg.get("why_it_matters", ""),
                    skills=sg.get("skills", [])
                ))

            # 3. Projects (Robust Fallback logic handled by prompt instructions, but kept safe here)
            projects = []
            for p in response.get("projects", []):
                projects.append(ProjectDetail(
                    title=p.get("title", "Project"),
                    difficulty=p.get("difficulty", "Beginner"),
                    description=p.get("description", ""),
                    deliverables=p.get("deliverables", []),
                    suggested_tools=p.get("suggested_tools", [])
                ))
            if intent_result.intent == IntentType.PROJECT_IDEAS and not projects:
                 # Minimal fallback if LLM returns nothing involved
                 projects = self._fallback_projects(intent_result.role or "General")

            # 4. Learning Plan
            learning_plan = None
            lp_data = response.get("learning_plan")
            if lp_data:
                schedule = []
                for week in lp_data.get("schedule", []):
                    schedule.append(WeeklySchedule(
                        week=week.get("week", 1),
                        focus=week.get("focus", ""),
                        courses=week.get("courses", []),
                        outcomes=week.get("outcomes", [])
                    ))
                learning_plan = LearningPlan(
                    weeks=lp_data.get("weeks"),
                    hours_per_day=lp_data.get("hours_per_day"),
                    schedule=schedule
                )
                
            # 5. Course Processing (Selection + Truncation)
            selected_course_ids = set()
            llm_courses = response.get("courses", [])
            
            # Map LLM enriched fields (reason, short desc) back to objects
            enriched_courses_map = {}
            for c in llm_courses:
                cid = c.get("course_id")
                if cid: 
                    selected_course_ids.add(cid)
                    enriched_courses_map[cid] = c

            if learning_plan:
                 for week in learning_plan.schedule:
                     for cid in week.courses: selected_course_ids.add(cid)

            # Filter & Enrich original course objects
            final_courses = []
            source_courses = courses_context if not selected_course_ids and courses_context else courses
            
            for course in source_courses:
                if course.course_id in selected_course_ids or (not selected_course_ids and course in courses_context):
                    # Create new object to avoid mutating original cache
                    new_course = course.model_copy()
                    
                    # Enrich from LLM response if available
                    enrich_data = enriched_courses_map.get(course.course_id, {})
                    
                    # Truncation Logic
                    full_desc = enrich_data.get("description_full") or course.description or ""
                    short_desc = enrich_data.get("description_short")
                    
                    if not short_desc:
                         # Manual truncation if LLM didn't provide
                         short_desc = full_desc[:220] + "..." if len(full_desc) > 220 else full_desc
                    
                    new_course.description_full = full_desc
                    new_course.description_short = short_desc
                    new_course.reason = enrich_data.get("reason")
                    new_course.cover = enrich_data.get("cover")
                    
                    final_courses.append(new_course)

            return answer, projects, final_courses, skill_groups, learning_plan

        except Exception as e:
            logger.error(f"Response building failed: {e}")
            if not courses:
                return "للأسف مش لاقي كورسات مناسبة حالياً. ممكن توضحلي أكتر؟", [], [], [], None
            
            return self._fallback_response(courses[:5])

    def _fallback_projects(self, topic: str) -> List[ProjectDetail]:
        """Generate template projects if LLM fails."""
        return [
            ProjectDetail(title=f"{topic} Starter", difficulty="Beginner", description="Basic app to practice fundamentals.", deliverables=["Console App"], suggested_tools=["IDE"]),
            ProjectDetail(title=f"{topic} Core App", difficulty="Intermediate", description="CRUD application with database.", deliverables=["Web App", "DB Schema"], suggested_tools=["Framework"]),
            ProjectDetail(title=f"{topic} Pro Suite", difficulty="Advanced", description="Full-scale solution.", deliverables=["Microservices", "CI/CD"], suggested_tools=["Docker"])
        ]

    def _fallback_response(self, courses: List[CourseDetail]):
        titles = "\n".join([f"- {c.title}" for c in courses])
        return f"لقيتلك الكورسات دي:\n{titles}", [], courses, [], None
