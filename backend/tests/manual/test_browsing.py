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
    async def generate(self, prompt, system_prompt=None, temperature=0.7):
        return "Mocked response"
    async def generate_json(self, prompt, system_prompt=None, temperature=0.7):
        return {"answer": "Mocked JSON"}

async def test_browsing():
    llm = MockLLM()
    router = IntentRouter(llm)
    builder = ResponseBuilder(llm)
    
    # Mock data_loader and its method
    # We need to mock it where it's imported/used
    import data_loader
    data_loader.data_loader.get_all_categories = lambda: [
        'Programming', 'Web Development', 'Mobile Development', 
        'Game Design', 'Data Security', 'Soft Skills', 'Marketing Skills'
    ]
    
    # Test 1: Broad Programming
    print("\n--- Test 1: Broad Programming ---")
    intent_res = await router.classify("انا عاوز اتعلم برمجة")
    print(f"Intent: {intent_res.intent}")
    print(f"Slots: {intent_res.slots}")
    
    answer, _, _, _, _, _, _ = await builder.build(
        intent_res, [], SkillValidationResult(), "انا عاوز اتعلم برمجة"
    )
    print(f"Answer:\n{answer}")
    
    # Test 2: General Catalog
    print("\n--- Test 2: General Catalog ---")
    intent_res = await router.classify("ايه الكورسات المتاحة؟")
    print(f"Intent: {intent_res.intent}")
    
    answer, _, _, _, _, _, _ = await builder.build(
        intent_res, [], SkillValidationResult(), "ايه الكورسات المتاحة؟"
    )
    print(f"Answer:\n{answer[:200]}...") # Truncated for list brevity

if __name__ == "__main__":
    asyncio.run(test_browsing())
