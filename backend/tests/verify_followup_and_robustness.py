import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from models import IntentType, IntentResult, ChatRequest, SkillValidationResult
from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder
from llm.groq_gateway import get_llm_gateway

async def test_followup_override():
    print("Testing Follow-up Override...")
    llm = get_llm_gateway()
    router = IntentRouter(llm)
    
    session_state = {"last_topic": "Leadership & Management"}
    message = "هل في كورسات؟"
    
    # This should trigger the new override
    result = await router.route(message, session_state)
    
    print(f"Intent detected: {result.intent}")
    print(f"Topic: {result.topic}")
    
    assert result.intent == IntentType.COURSE_SEARCH
    assert result.topic == "Leadership & Management"
    print("✅ Follow-up Override test passed!")

async def test_response_builder_robustness():
    print("\nTesting ResponseBuilder Robustness...")
    llm = get_llm_gateway()
    rb = ResponseBuilder(llm)
    
    intent_result = IntentResult(intent=IntentType.COURSE_SEARCH, topic="Python")
    
    # We will pass something that might cause a crash if not handled
    try:
        # Mocking an error by passing None where a list is expected or similar
        # Actually, let's just test that it handles general exceptions
        # We can't easily force an exception without modifying the code, 
        # but we can verify it doesn't crash on standard inputs.
        res = await rb.build(
            intent_result=intent_result,
            courses=[],
            skill_result=SkillValidationResult(validated_skills=[]),
            user_message="test",
            context={}
        )
        print(f"Answer: {res.answer}")
        assert res.intent is not None
    except Exception as e:
        print(f"❌ ResponseBuilder crashed: {e}")
        assert False
    print("✅ ResponseBuilder Robustness test passed (did not crash)!")

async def main():
    try:
        await test_followup_override()
        await test_response_builder_robustness()
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
