
import asyncio
import logging
from typing import List
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.pipeline.response_builder import ResponseBuilder
from backend.models import IntentResult, IntentType, CourseDetail, SkillValidationResult, SkillGroup

async def test_v10_logic():
    # 1. Mock LLM
    class MockLLM:
        async def generate_json(self, prompt, system_prompt, temperature):
            logger.info(f"Prompt sent to LLM:\n{prompt[:200]}...")
            # Return a V10 compliant dummy response
            return {
                "intent": "CAREER_GUIDANCE",
                "include_plan": False,
                "include_projects": True,
                "confidence": 0.95,
                "language": "ar",
                "role": "Data Analyst",
                "answer": "هذا هو مسار محلل البيانات.",
                "required_skills": {
                    "core": [
                        { "skill": "SQL", "why": "للتنقيب عن البيانات", "course_ids": ["c1"] }
                    ],
                    "supporting": [
                        { "skill": "Excel", "why": "لتحليل البيانات", "course_ids": ["c2"] }
                    ]
                },
                "recommended_courses": [
                    { "course_id": "c1", "title": "SQL Mastery", "fit": "core", "why_recommended": "Essential" }
                ],
                "all_relevant_courses": [
                    { "course_id": "c1", "title": "SQL Mastery", "fit": "core" },
                    { "course_id": "c2", "title": "Excel Basics", "fit": "supporting" }
                ],
                "learning_plan": None,
                "projects": [
                    { "title": "Churn Analysis", "difficulty": "Intermediate", "description": "Analyzing customer churn." }
                ],
                "followup_question": "هل تريد التعرف على مهارات أكثر؟"
            }

    llm = MockLLM()
    builder = ResponseBuilder(llm)

    # 2. Setup Input Data
    intent = IntentResult(intent=IntentType.CAREER_GUIDANCE, role="Data Analyst", confidence=1.0)
    courses = [
        CourseDetail(course_id="c1", title="SQL Mastery", level="Intermediate", category="Data", instructor="Instructor A", duration_hours=10, description="Deep SQL"),
        CourseDetail(course_id="c2", title="Excel Basics", level="Beginner", category="Tools", instructor="Instructor B", duration_hours=5, description="Spreadsheets")
    ]
    skill_result = SkillValidationResult(validated_skills=["SQL", "Excel"])
    user_message = "عاوز ابقى داتا اناليست"

    # 3. Execution
    logger.info("\n--- Running Build ---")
    answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant = await builder.build(
        intent, courses, skill_result, user_message, context={}
    )

    print(f"DEBUG: Answer = '{answer}'")
    print(f"DEBUG: Projects = {projects}")
    print(f"DEBUG: Courses = {final_courses}")
    print(f"DEBUG: AllRelevant = {all_relevant}")
    print(f"DEBUG: SkillGroups = {skill_groups}")

    # 4. Assertions
    logger.info(f"Answer: {answer}")
    logger.info(f"Projects: {len(projects)}")
    logger.info(f"Final Courses (Tier 1): {len(final_courses)}")
    logger.info(f"All Relevant (Tier 2): {len(all_relevant)}")
    logger.info(f"Skill Groups: {len(skill_groups)}")
    
    assert "محلل البيانات" in answer or "Data Analyst" in answer
    assert len(projects) == 1
    assert len(final_courses) == 1
    assert len(all_relevant) == 2
    assert learning_plan is None # Strict policy
    
    for sg in skill_groups:
        for s in sg.skills:
             logger.info(f"Skill: {s.name}, IDs: {s.course_ids}")
             assert s.course_ids is not None
             assert len(s.course_ids) > 0

    logger.info("\nSUCCESS: V10 Logic Verification Passed (Mock LLM)!")

if __name__ == "__main__":
    asyncio.run(test_v10_logic())
