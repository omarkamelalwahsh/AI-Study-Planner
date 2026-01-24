import asyncio
import json
import sys
from unittest.mock import MagicMock

# Mock database and models
mock_db = MagicMock()
sys.modules['app.database'] = mock_db
mock_settings = MagicMock()
mock_settings.groq_api_key = "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"
mock_settings.groq_max_retries = 2
mock_settings.groq_model = "llama-3.1-8b-instant"
mock_settings.groq_timeout_seconds = 20
sys.modules['app.config'] = MagicMock()
sys.modules['app.config'].settings = mock_settings

# For Arabic output in Windows console
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from app.router import classify_intent
    from app.generator import generate_guidance_plan, generate_final_response
    from app.skills import extract_skills_and_areas
except ImportError as e:
    print(f"Import error: {e}")

async def test_rules():
    test_cases = [
        {
            "name": "Domain Authority Check (Technical Role vs Non-Technical Goal)",
            "query": "I am a backend developer. I want to learn video editing for my hobby."
        },
        {
            "name": "Silent Typo Correction",
            "query": "gow to become a data enginer"
        },
        {
            "name": "Honesty Check (Zero Courses Match)",
            "query": "I want to learn Quantum Computing for Space Travel",
            "mock_grounded": []
        },
        {
            "name": "Arabic Language Mirroring",
            "query": "عايز اتعلم بايثون للمبتدئين"
        }
    ]
    
    print("--- STARTING ABSOLUTE RULES VERIFICATION ---")
    import time
    for tc in test_cases:
        time.sleep(5)
        print(f"\nTEST: {tc['name']}")
        print(f"QUERY: {tc['query']}")
        try:
            # Stage 0: Router
            router_out = classify_intent(tc['query'])
            print(f"THINKING: {router_out.thinking}")
            print(f"INTENT: {router_out.intent}")
            print(f"CATEGORY: {router_out.target_categories}")
            
            # Stage 1: Guidance Plan
            plan = generate_guidance_plan(tc['query'], router_out)
            print(f"GUIDANCE INTRO: {plan.get('guidance_intro')}")
            
            # Stage 4: Final Rendering (Using mock or real flow)
            # We mock grounded_courses if specified to test honesty
            grounded = tc.get("mock_grounded", [])
            response = generate_final_response(
                user_question=tc['query'],
                guidance_plan=plan,
                grounded_courses=grounded,
                language=router_out.user_language
            )
            print(f"FINAL RESPONSE (FIRST 200 CHARS):\n{response[:200]}...")
            
        except Exception as e:
            print(f"ERROR in {tc['name']}: {e}")
            
    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_rules())
