import asyncio
import json
import sys
from unittest.mock import MagicMock

# Mock database and models before importing app.router
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

# Try to import after mocking
try:
    from app.router import classify_intent
    from app.generator import generate_guidance_plan
except ImportError:
    # If it still fails, we'll just test the prompts directly
    pass

async def test_flow():
    test_queries = [
        "I want to learn how to manage a data science team",
        "How to become a web developer specialized in React",
        "عايز اتعلم برمجة بايثون عشان اشتغل في ال AI"
    ]
    
    print("--- STARTING VERIFICATION ---")
    for q in test_queries:
        print(f"\nQUERY: {q}")
        try:
            # Test Router
            router_out = classify_intent(q)
            print(f"INTENT: {router_out.intent}")
            print(f"CATEGORIES: {router_out.target_categories}")
            print(f"THINKING: {router_out.thinking}")
            
            # Test Guidance Planner (optional, mock results)
            plan = generate_guidance_plan(q, router_out)
            print(f"INTRO: {plan.get('guidance_intro')}")
            print(f"AREAS: {[a.get('area') for a in plan.get('core_areas', [])]}")
            
        except Exception as e:
            print(f"ERROR: {e}")
    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_flow())
