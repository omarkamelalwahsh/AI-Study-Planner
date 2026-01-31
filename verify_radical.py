import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from pipeline.response_builder import ResponseBuilder
from llm.base import LLMBase
from models import IntentType, IntentResult, CourseDetail, SkillValidationResult

class MockDiscoveryLLM(LLMBase):
    async def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=1024):
        return "Mock response"

    async def generate_json(self, prompt, system_prompt=None, temperature=0.7):
        if "CATALOG_BROWSING" in prompt or "ايه الكورسات" in prompt:
            return {
                "intent": "CATALOG_BROWSING",
                "mode": "browsing",
                "answer": "Check these categories!",
                "available_categories": ["Programming", "Sales", "HR"],
                "followup_question": "Which one?"
            }
        else:
            return {
                "intent": "CAREER_GUIDANCE",
                "mode": "courses_only",
                "answer": "Milestone 1, 2, 3",
                "required_skills": {
                    "core": [
                        {"skill": "programming", "why": "Core usage"},
                        {"skill": "Hacked", "why": "No evidence"}
                    ]
                },
                "recommended_courses": [
                    {"course_id": "uuid-1", "title": "Intro to Programming", "fit": "core", "why_recommended": "Base"}
                ]
            }

async def verify_radical():
    llm = MockDiscoveryLLM()
    builder = ResponseBuilder(llm)
    
    # 1. Test Direct Catalog Browsing (New)
    print("--- Testing Direct Catalog Browsing ---")
    intent_disco = IntentResult(intent=IntentType.CATALOG_BROWSING, value="CATALOG_BROWSING")
    ans, _, _, _, _, _, _, cb_obj, mode, followup, refined_intent = await builder.build(
        intent_disco, [], SkillValidationResult(), "ايه الكورسات المتاحة؟", 
        available_categories=["Programming", "Data"]
    )
    print(f"Mode: {mode}") # Should be category_explorer
    print(f"Refined Intent: {refined_intent}")
    print(f"Answer Sample: {ans[:50]}...")
    
    # 2. Test Broad Query (New)
    print("\n--- Testing Broad Query (Programming) ---")
    intent_broad = IntentResult(intent=IntentType.CAREER_GUIDANCE, value="CAREER_GUIDANCE")
    ans, _, _, _, _, _, _, cb_obj, mode, followup, refined_intent = await builder.build(
        intent_broad, [], SkillValidationResult(), "اتعلم برمجة"
    )
    print(f"Mode: {mode}") # Should be category_explorer
    print(f"Answer Sample: {ans[:50]}...")

    # 3. Test Grounding (Skill filtering)
    print("\n--- Testing Career Guidance Grounding ---")
    courses = [CourseDetail(course_id="uuid-1", title="Intro to Programming")]
    # Correct mock for DataLoader (Singleton)
    from data_loader import data_loader
    data_loader.all_skills_set.add("programming")
    
    skill_res = SkillValidationResult(validated_skills=["programming"])
    intent_guidance = IntentResult(intent=IntentType.CAREER_GUIDANCE, role="Developer", value="CAREER_GUIDANCE")
    
    ans, projs, final_courses, skill_groups, plan, dash, all_rel, cb_obj, mode, followup, refined_intent = await builder.build(
        intent_guidance, courses, skill_res, "ازاي ابقى مبرمج"
    )
    
    print(f"Mode: {mode}")
    print(f"Skill Groups: {len(skill_groups)}")
    if skill_groups:
        skills = skill_groups[0].skills
        print(f"Validated skills returned: {[s.label for s in skills]}")
        # 'Hacked' should be filtered out by validator

    # 4. Test Grounded QA (Definition + Catalog Link)
    print("\n--- Testing Grounded QA (Definition) ---")
    intent_qa = IntentResult(intent=IntentType.GENERAL_QA, value="GENERAL_QA")
    # Simulate technical definition question
    ans, _, _, _, _, _, _, _, mode, _, _ = await builder.build(
        intent_qa, courses, skill_res, "يعني ايه برمجة؟"
    )
    print(f"Mode: {mode}") # Should be answer_only
    print(f"Answer Sample: {ans[:100]}...")

if __name__ == "__main__":
    asyncio.run(verify_radical())
