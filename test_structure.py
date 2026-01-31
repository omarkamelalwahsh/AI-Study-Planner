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
        # Return generic for non-catalog cases
        return {"answer": "Mocked JSON response"}

async def test_structure():
    llm = MockLLM()
    router = IntentRouter(llm)
    builder = ResponseBuilder(llm)
    
    # Mock data_loader
    import data_loader
    data_loader.data_loader.get_all_categories = lambda: [
        'Programming', 'Web Development', 'Mobile Development', 
        'Game Design', 'Data Security', 'Networking', 'Soft Skills', 
        'Marketing Skills', 'Business Fundamentals', 'Human Resources'
    ]
    
    cases = [
        ("انا عاوز اتعلم برمجة", "Broad Programming"),
        ("ايه الكورسات المتاحة؟", "General Catalog"),
        ("مش عارف أتعلم ايه", "I don't know what to learn")
    ]
    
    for query, label in cases:
        print(f"\n--- Testing {label}: '{query}' ---")
        intent_res = await router.classify(query)
        print(f"Intent: {intent_res.intent}")
        
        result = await builder.build(
            intent_res, [], SkillValidationResult(), query
        )
        
        # Result tuple index mapping (based on build() return):
        # 0: answer, 1: projects, 2: courses, 3: skill_groups, 4: learning_plan, 
        # 5: cv_dashboard, 6: all_relevant, 7: category_groups, 8: mode, 9: followup_question
        
        print(f"Answer: {result[0]}")
        print(f"Mode: {result[8]}")
        print(f"Follow-up: {result[9]}")
        print(f"Groups count: {len(result[7])}")
        for g in result[7]:
            print(f"  Group '{g.group_title}': {g.categories}")

if __name__ == "__main__":
    asyncio.run(test_structure())
