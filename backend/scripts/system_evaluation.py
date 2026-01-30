import httpx
import asyncio
import json
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8001"
SESSION_ID = str(uuid.uuid4())

async def chat(message: str, session_id: str):
    logger.info(f"\n[USER]: {message}")
    # Increased timeout to 60s as LLM + RAG can be slow
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": message, "session_id": session_id}
        )
        if response.status_code != 200:
            logger.error(f"Error: {response.status_code} - {response.text}")
            return None
        return response.json()

def evaluate_response(name: str, response: dict, assertions: dict):
    logger.info(f"--- Evaluating: {name} ---")
    if not response:
        logger.error(f"FAIL: {name} - No response received")
        return False
    
    passed = True
    for key, value in assertions.items():
        # Check intent (Allow list for flexible mapping)
        if key == "intent":
            expected = [value] if isinstance(value, str) else value
            if response.get("intent") not in expected:
                logger.error(f"FAIL: Expected intent {expected}, got {response.get('intent')}")
                passed = False
        
        # Check if list is not empty
        elif key == "has_courses" and value and not response.get("courses"):
            logger.error(f"FAIL: Expected courses, but list is empty")
            passed = False
            
        # Check if list IS empty
        elif key == "no_courses" and value and response.get("courses"):
            logger.error(f"FAIL: Expected no courses, but got {len(response.get('courses'))}")
            passed = False

        # Check for specific words (Arabic/Eng)
        elif key == "contains_any":
            if not any(v.lower() in response.get("answer", "").lower() for v in value):
                logger.error(f"FAIL: Answer should contain one of {value}")
                passed = False
            
        # Check projects
        elif key == "has_projects" and value and not response.get("projects"):
            logger.error(f"FAIL: Expected projects, but list is empty")
            passed = False
            
        # Check learning plan
        elif key == "no_plan" and value and response.get("learning_plan"):
            logger.error(f"FAIL: Expected no learning plan, but found one")
            passed = False

        # V10: Check Two-Tier course output
        elif key == "has_all_relevant" and value and not response.get("all_relevant_courses"):
            logger.error(f"FAIL: Expected all_relevant_courses, but list is empty")
            passed = False
        
        # V10: Check skill grounding
        elif key == "skills_grounded" and value:
            groups = response.get("skill_groups", [])
            for g in groups:
                 for s in g.get("skills", []):
                      if not s.get("course_ids"):
                           logger.error(f"FAIL: Skill '{s.get('name')}' is not grounded (no course_ids)")
                           passed = False

    if passed:
        logger.info(f"PASS: {name} consistent with expectations.")
    return passed

async def main():
    logger.info("Starting robust System-Wide Pipeline Evaluation...")
    logger.info(f"Session ID: {SESSION_ID}")

    # TEST 1: Initial Search
    resp1 = await chat("إيه هي كورسات الويب؟", SESSION_ID)
    evaluate_response("Test 1: Web Search", resp1, {
        "intent": "COURSE_SEARCH",
        "has_courses": True,
        "contains_any": ["HTML", "ويب", "front", "فرونت"]
    })

    # TEST 2: Pagination (Show More)
    resp2 = await chat("في غيرهم؟", SESSION_ID)
    evaluate_response("Test 2: Pagination", resp2, {
        "intent": ["FOLLOW_UP", "COURSE_SEARCH"], # Flexible
        "has_courses": True
    })
    
    # TEST 3: Domain Switch (Back-end)
    resp3 = await chat("طيب انا دلوقتي عاوز ابقى باك اند", SESSION_ID)
    evaluate_response("Test 3: Domain Switch (Back-end)", resp3, {
        "intent": "CAREER_GUIDANCE",
        "has_courses": True,
        "has_projects": True,
        "contains_any": ["Python", "بايثون", "Node", "نود", "Sql", "باك"]
    })

    # TEST 4: Soft Skills (Intent Guard)
    resp4 = await chat("ممكن تقولي مهارات التواصل؟", SESSION_ID)
    evaluate_response("Test 4: Soft Skills", resp4, {
        "intent": "CAREER_GUIDANCE",
        "has_projects": True,
        "no_plan": True
    })

    # V10 TEST 6: Strict Plan Policy (No plan for guidance)
    logger.info("\n--- V10: Verifying Strict Plan Policy ---")
    resp6 = await chat("بقولك ايه انا عاوز ابقى داتا اناليست", SESSION_ID)
    evaluate_response("Test 6: CAREER_GUIDANCE No Plan", resp6, {
        "intent": "CAREER_GUIDANCE",
        "no_plan": True,
        "has_courses": True,
        "has_all_relevant": True,
        "skills_grounded": True
    })

    # V10 TEST 7: Skill Grounding check
    logger.info("\n--- V10: Verifying Skill Grounding ---")
    evaluate_response("Test 7: Skill Grounding", resp6, {
        "skills_grounded": True
    })

    # V10 TEST 8: Two-Tier Course Layout
    logger.info("\n--- V10: Verifying Two-Tier Layout ---")
    evaluate_response("Test 8: Two-Tier courses", resp6, {
        "has_courses": True,
        "has_all_relevant": True
    })

    logger.info("\nEvaluation Complete.")

if __name__ == "__main__":
    asyncio.run(main())
