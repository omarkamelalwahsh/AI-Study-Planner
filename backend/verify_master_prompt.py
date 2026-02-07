
import json
import asyncio
from unittest.mock import MagicMock
from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder
from models import IntentType, IntentResult, SkillValidationResult, SemanticResult

async def verify():
    llm = MagicMock()
    router = IntentRouter(llm)
    
    scenarios = [
        ("How do I become a successful Sales Manager?", IntentType.CAREER_GUIDANCE, "Role based"),
        ("I want to learn Marketing but I’m lost", IntentType.SAFE_FALLBACK, "Lost + Track -> Fallback"),
        ("Recommend courses for SQL", IntentType.COURSE_SEARCH, "Explicit course request"),
        ("Show me your categories", IntentType.CATALOG_BROWSE, "Catalog browse")
    ]
    
    print("--- MANUAL OVERRIDES VERIFICATION ---")
    for msg, expected, desc in scenarios:
        res = router._check_manual_overrides(msg)
        actual = res.intent if res else "NONE"
        # status = "PASSED" if str(actual) == str(expected) else "FAILED"
        status = "PASSED" if actual == expected else "FAILED"
        print(f"Scenario: {desc} | Msg: '{msg}'")
        print(f"  Expected: {expected} | Actual: {actual} | Status: {status}")

    print("\n--- SCHEMA COMPLIANCE VERIFICATION ---")
    llm.generate_json.return_value = {
        "success": True,
        "intent": "COURSE_SEARCH",
        "message": "Here are the SQL courses.",
        "categories": ["SQL", "Data"],
        "courses": [
            {
                "course_id": "c1", "title": "Intro to Marketing", "category": "Marketing", 
                "level": "Beginner", "description_short": "Learn basics",
                "action": {"type": "OPEN_COURSE_DETAILS", "course_id": "c1"}
            }
        ],
        "errors": []
    }
    
    builder = ResponseBuilder(llm)
    intent_res = IntentResult(intent=IntentType.COURSE_SEARCH)
    try:
        chat_res = await builder.build(
            intent_res, [], SkillValidationResult(validated_skills=[]), 
            "courses for SQL", {}, 
            SemanticResult(primary_domain="SQL", is_in_catalog=True)
        )
        
        print(f"Success field: {chat_res.success}")
        print(f"Message field: {chat_res.message}")
        print(f"Intent field: {chat_res.intent}")
        print(f"Categories present: {len(chat_res.categories) > 0}")
        print("Schema check: PASSED")
    except Exception as e:
        print(f"Schema check: FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify())
