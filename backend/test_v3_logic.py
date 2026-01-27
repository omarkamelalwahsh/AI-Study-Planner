
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult
from llm.base import LLMBase

# Mock LLM
class MockLLM(LLMBase):
    async def generate_json(self, prompt, **kwargs):
        # Simulate failure for project ideas to test fallback
        if "project" in prompt.lower():
            return {} 
        return {"intent": "COURSE_SEARCH"}

    async def generate(self, prompt, **kwargs):
        return "mock"

async def test_v3_logic():
    print("Testing V3 Logic...")
    llm = MockLLM()
    router = IntentRouter(llm)
    builder = ResponseBuilder(llm)

    # 1. Test Intent Overrides
    print("\n[Test 1] Intent Overrides")
    
    # Follow-up
    res = await router.classify("كمان")
    print(f"Input 'كمان': {res.intent} (Expected: FOLLOW_UP)")
    
    res = await router.classify("show more")
    print(f"Input 'show more': {res.intent} (Expected: FOLLOW_UP)")

    # Concept Explain
    res = await router.classify("what is python")
    print(f"Input 'what is python': {res.intent} (Expected: CONCEPT_EXPLAIN)")
    
    res = await router.classify("ايه هي البرمجة")
    print(f"Input 'ايه هي البرمجة': {res.intent} (Expected: CONCEPT_EXPLAIN)")
    
    # 2. Test Project Fallback
    print("\n[Test 2] Project Fallback")
    intent_res = IntentResult(intent=IntentType.PROJECT_IDEAS, role="Python Developer")
    skill_res = SkillValidationResult(validated_skills=["python"])
    courses = [] # No courses needed for this test
    
    # This should trigger _generate_fallback_projects because MockLLM returns empty dict for projects
    answer, projects, selected = await builder.build(intent_res, courses, skill_res, "project ideas")
    
    print(f"Projects returned: {len(courses)}") # Correction: printing len(projects)
    print(f"Projects count: {len(projects)}")
    if len(projects) == 3:
        print("PASS: Fallback generated 3 projects")
        print(f"Project 1: {projects[0].title}")
    else:
        print(f"FAIL: Expected 3 projects, got {len(projects)}")

if __name__ == "__main__":
    asyncio.run(test_v3_logic())
