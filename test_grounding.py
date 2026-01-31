import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from pipeline.response_builder import ResponseBuilder
from llm.base import LLMBase
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult

class MockLLM(LLMBase):
    async def generate_json(self, prompt, system_prompt=None, temperature=0.7):
        # Simulate LLM trying to invent a skill "Invented Skill"
        return {
            "intent": "CAREER_GUIDANCE",
            "answer": "Milestone 1, 2, 3",
            "required_skills": {
                "core": [
                    {"skill": "programming", "label": "البرمجة", "why": "Core", "course_ids": ["uuid-1"]},
                    {"skill": "Invented Skill", "label": "Hacked Skill", "why": "No evidence", "course_ids": ["uuid-2"]}
                ]
            },
            "recommended_courses": [
                {"course_id": "uuid-1", "title": "Intro to Programming", "fit": "core", "why_recommended": "Base"}
            ],
            "followup_question": "Roadmap?"
        }

async def test_grounding():
    llm = MockLLM()
    builder = ResponseBuilder(llm)
    
    courses = [
        CourseDetail(course_id="uuid-1", title="Intro to Programming", category="Programming", description="Desc")
    ]
    
    # Only "programming" is validated
    skill_res = SkillValidationResult(validated_skills=["programming"])
    intent_res = IntentResult(intent=IntentType.CAREER_GUIDANCE, role="Developer")
    
    ans, projs, f_courses, s_groups, l_plan, dashboard, a_rel, _, _, followup = await builder.build(
        intent_res, courses, skill_res, "test message"
    )
    
    print(f"Groups count: {len(s_groups)}")
    if s_groups:
        skills = s_groups[0].skills
        print(f"Skills in group: {[s.name for s in skills]}")
        # "Invented Skill" should be filtered out because it's not in validated_skills

if __name__ == "__main__":
    asyncio.run(test_grounding())
