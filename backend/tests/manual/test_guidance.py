import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder
from llm.base import LLMBase
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult

class MockLLM(LLMBase):
    async def generate_json(self, prompt, system_prompt=None, temperature=0.7):
        # Simulate LLM following the new instructions
        return {
            "intent": "CAREER_GUIDANCE",
            "answer": "لتصبح مبرمجًا ناجحًا، تحتاج لاتباع هذه الخطوات:\n1. تعلم الأساسيات.\n2. اختر تخصصًا.\n3. ابدأ بمشاريع حقيقية.",
            "role": "مبرمج ناجح",
            "required_skills": {
                "core": [
                    {"skill": "Logic", "why": "Essential for coding", "course_ids": ["uuid-1"]}
                ]
            },
            "recommended_courses": [
                {"course_id": "uuid-1", "title": "Intro to Logic", "fit": "core", "why_recommended": "Builds base."}
            ],
            "followup_question": "تحب خطة أسبوعية (Roadmap) ولا ترشيح كورسات فقط؟"
        }

async def test_guidance():
    llm = MockLLM()
    router = IntentRouter(llm)
    builder = ResponseBuilder(llm)
    
    courses = [
        CourseDetail(course_id="uuid-1", title="Intro to Logic", category="Programming", description="Desc")
    ]
    
    intent_res = IntentResult(intent=IntentType.CAREER_GUIDANCE, role="مبرمج ناجح")
    
    answer, projects, final_courses, skill_groups, plan, dashboard, all_rel, _, _, followup = await builder.build(
        intent_res, courses, SkillValidationResult(), "ازاي اكون مبرمج ناجح"
    )
    
    print(f"Answer:\n{answer}")
    print(f"Follow-up: {followup}")
    print(f"Skills count: {len(skill_groups)}")
    if skill_groups:
        print(f"Skill 1 name: {skill_groups[0].skills[0].name}")
        print(f"Skill 1 why: {skill_groups[0].skills[0].why}")

if __name__ == "__main__":
    asyncio.run(test_guidance())
