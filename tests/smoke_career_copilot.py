import sys
import os
import uuid
import logging
from typing import Dict, Any

# Mocking DB and search for local service tests
class MockDB:
    def add(self, item): pass
    def commit(self): pass
    def refresh(self, item): 
        if hasattr(item, 'id') and not item.id:
            item.id = uuid.uuid4()

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.services.career_copilot.intent_router import IntentRouter
from app.services.career_copilot.role_advisor import RoleAdvisor
from app.services.career_copilot.course_recommender import CourseRecommender
from app.services.career_copilot.study_planner import StudyPlanner
from app.services.career_copilot.response_composer import ResponseComposer
from app.schemas_career import UserConstraints

def test_full_pipeline_vague():
    print("\n--- Testing Pipeline: Vague Query ---")
    message = "I want to start a new career in tech"
    
    # 1. Intent
    import app.services.career_copilot.intent_router as ir
    print(f"DEBUG: Importing IntentRouter from {ir.__file__}")
    intent = IntentRouter.parse_intent(message)
    print(f"Intent Confidence: {intent.confidence_level}")
    assert intent.confidence_level == "vague"
    
    # 2. Advisor
    advisor = RoleAdvisor()
    role_info = advisor.get_role_info(intent.career_goal or "General")
    print(f"Role: {role_info['role']}")
    assert "General" in role_info['role'] or "Professional" in role_info['role']
    
    # 3. Recommender (requires SearchEngine to be mockable or initialized)
    # For smoke test, we'll assume it returns something or we skip search calls
    
    # 4. Response
    constraints = UserConstraints()
    plan_data = {"plan_type": "custom", "coverage_score": 0.1, "plan_weeks": []}
    
    output = ResponseComposer.compose(
        session_id=uuid.uuid4(),
        intent=intent,
        role_info=role_info,
        plan_data=plan_data,
        recommended_courses=[],
        lang_policy="en"
    )
    
    print(f"Summary: {output.summary}")
    assert "assess your current level" in output.summary.lower()
    print("Vague query test PASSED.")

def test_full_pipeline_clear_ar():
    print("\n--- Testing Pipeline: Clear Arabic Query ---")
    message = "عاوز ابقى مهندس برمجيات" # "I want to be a software engineer"
    
    intent = IntentRouter.parse_intent(message)
    print(f"Language detected: {intent.language}")
    print(f"Career Goal: {intent.career_goal}")
    assert intent.career_goal == "Software Engineer"
    
    advisor = RoleAdvisor()
    role_info = advisor.get_role_info(intent.career_goal)
    assert "Software Engineer" in role_info['role']
    
    plan_data = {"plan_type": "our_courses", "coverage_score": 0.8, "plan_weeks": []}
    output = ResponseComposer.compose(
        session_id=uuid.uuid4(),
        intent=intent,
        role_info=role_info,
        plan_data=plan_data,
        recommended_courses=[],
        lang_policy="ar"
    )
    
    assert "خارطة طريق" in output.summary
    print("Clear Arabic query test PASSED.")

if __name__ == "__main__":
    try:
        test_full_pipeline_vague()
        test_full_pipeline_clear_ar()
        print("\nALL PRODUCTION SMOKE TESTS PASSED.")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
