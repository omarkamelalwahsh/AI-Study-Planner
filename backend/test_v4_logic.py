
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.response_builder import ResponseBuilder
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult, SkillGroup, LearningPlan
from llm.base import LLMBase

# Mock LLM
class MockLLM(LLMBase):
    def __init__(self, mode="truncation"):
        self.mode = mode

    async def generate_json(self, prompt, **kwargs):
        if self.mode == "truncation":
            return {
                "intent": "COURSE_SEARCH",
                "answer": "Here are courses.",
                "courses": [
                    {
                        "course_id": "c1",
                        "title": "Long Course",
                        # LLM does NOT return description_short here, testing backend truncation
                        "reason": "Good match"
                    }
                ]
            }
        elif self.mode == "concept":
            return {
                "intent": "CONCEPT_EXPLAIN",
                "answer": "Explanation of concept.",
                "courses": [] # Should be empty or ignored
            }
        elif self.mode == "schema":
            return {
                "intent": "CAREER_GUIDANCE",
                "answer": "Guidance.",
                "skill_groups": [{"skill_area": "A", "why_it_matters": "B", "skills": ["C"]}],
                "learning_plan": {"weeks": 4, "hours_per_day": 2, "schedule": []},
                "courses": []
            }
        return {}

    async def generate(self, prompt, **kwargs):
        return "mock"

async def test_v4_logic():
    print("Testing V4 Logic...")
    
    # 1. Test Description Truncation
    print("\n[Test 1] Description Truncation")
    llm = MockLLM(mode="truncation")
    builder = ResponseBuilder(llm)
    
    long_desc = "This is a very long description. " * 20 # > 400 chars
    courses = [CourseDetail(course_id="c1", title="Long Course", description=long_desc)]
    intent_res = IntentResult(intent=IntentType.COURSE_SEARCH)
    skill_res = SkillValidationResult(validated_skills=[])
    
    _, _, final_courses, _, _ = await builder.build(intent_res, courses, skill_res, "msg")
    
    c = final_courses[0]
    print(f"Original Length: {len(c.description_full)}")
    print(f"Short Length: {len(c.description_short)}")
    print(f"Short Content: {c.description_short}")
    
    if len(c.description_short) <= 223 and c.description_short.endswith("..."): # 220 + 3 dots
        print("PASS: Truncation works")
    else:
        print("FAIL: Truncation failed")
        
    # 2. Test Intent Separation (Concept)
    print("\n[Test 2] Intent Separation (Concept)")
    llm = MockLLM(mode="concept")
    builder = ResponseBuilder(llm)
    
    intent_res = IntentResult(intent=IntentType.CONCEPT_EXPLAIN)
    # Even if we pass courses, they should not be returned for pure concept unless requested
    # But wait, ResponseBuilder logic filters based on what LLM returns in 'courses' list.
    # LLM Mock returns empty list.
    _, _, final_courses, _, _ = await builder.build(intent_res, courses, skill_res, "what is x")
    
    if not final_courses:
        print("PASS: No courses returned for Concept intent")
    else:
        print(f"FAIL: Courses returned: {len(final_courses)}")

    # 3. Test Output Format (Schema)
    print("\n[Test 3] Output Schema (Skill Group & Plan)")
    llm = MockLLM(mode="schema")
    builder = ResponseBuilder(llm)
    intent_res = IntentResult(intent=IntentType.CAREER_GUIDANCE)
    
    _, _, _, skill_groups, learning_plan = await builder.build(intent_res, [], skill_res, "career path")
    
    if skill_groups and skill_groups[0].skill_area == "A":
        print("PASS: Skill Groups parsed")
    else:
        print("FAIL: Skill Groups missing")
        
    if learning_plan and learning_plan.weeks == 4:
        print("PASS: Learning Plan parsed")
    else:
        print("FAIL: Learning Plan missing")

if __name__ == "__main__":
    asyncio.run(test_v4_logic())
