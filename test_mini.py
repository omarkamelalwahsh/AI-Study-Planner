import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder
from llm.base import LLMBase

class MockLLM(LLMBase):
    async def generate_json(self, *args, **kwargs): return {"answer": "mock"}

async def check():
    router = IntentRouter(MockLLM())
    builder = ResponseBuilder(MockLLM())
    import data_loader
    data_loader.data_loader.get_all_categories = lambda: ["Programming", "Web Development", "Sales", "Soft Skills"]
    
    # Check Manual Override
    res = router._check_manual_overrides("عايز اتعلم برمجة")
    print(f"Intent 1: {res.intent if res else 'None'}")
    print(f"Topic Slot: {res.slots.get('topic') if res and res.slots else 'None'}")
    
    # Check Response Builder
    ans = await builder.build(res, [], None, "msg")
    print(f"Answer Sample: {ans[0][:50]}...")
    print(f"Groups count: {len(ans[7])}")

if __name__ == "__main__":
    asyncio.run(check())
