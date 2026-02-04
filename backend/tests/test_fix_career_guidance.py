import asyncio
import sys
import os
import logging

# Setup path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.response_builder import ResponseBuilder
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult, SkillGroup, LearningPlan
from llm.base import LLMBase

# Configure logging to see the output
logging.basicConfig(level=logging.INFO)

class MockLLM(LLMBase):
    async def generate_json(self, prompt, **kwargs):
        # SIMULATE THE BUG: LLM returns include_plan=False, but leaks a plan in 'role' and 'followup_question'
        return {
            "intent": "CAREER_GUIDANCE",
            "include_plan": False,
            "role": "Sales Manager\n\nPhase 1: Foundations\nWeek 1: Introduction to Sales...",
            "skills_required": {
                "core": [{"skill": "Communication", "why": "Important"}],
                "supporting": []
            },
            "recommended_courses": [],
            "learning_plan": None, # or empty dict
            "projects": [],
            "followup_question": "Do you want a plan? Also here is Phase 1: Week 1..."
        }

    async def generate(self, prompt, **kwargs):
        return "mock"

async def test_career_guidance_fix():
    print("Testing Career Guidance Fix...")
    llm = MockLLM()
    builder = ResponseBuilder(llm)
    
    intent_res = IntentResult(intent=IntentType.CAREER_GUIDANCE, role="Sales Manager")
    skill_res = SkillValidationResult(validated_skills=[])
    courses = [] # No courses for this test needed
    
    answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard = await builder.build(intent_res, courses, skill_res, "i want to be sales manager")
    
    print("\n--- Final Answer ---")
    print(answer)
    print("--------------------\n")
    
    # Assertions
    # 1. Check if 'role' description was truncated
    assert "Phase 1" not in answer, "FAIL: 'Phase 1' leaked into the answer/role description"
    assert "Week 1" not in answer, "FAIL: 'Week 1' leaked into the answer/role description"
    assert "Sales Manager" in answer, "FAIL: Role title missing"
    
    # 2. Check if 'followup_question' was cleaned
    # The answer usually ends with the followup question
    assert "Do you want a structured plan" in answer, "FAIL: Follow-up question not present or incorrect"
    assert "Also here is Phase 1" not in answer, "FAIL: Follow-up question has leaked plan"
    
    # 3. Check if 'learning_plan' is None
    assert learning_plan is None, "FAIL: Learning Plan object should be None"
    
    print("PASS: Career Guidance Fix Verified!")

if __name__ == "__main__":
    asyncio.run(test_career_guidance_fix())
