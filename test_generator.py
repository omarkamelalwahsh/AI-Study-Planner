import sys
import os
import json
from unittest.mock import MagicMock

# Attempt to resolve paths
sys.path.append(os.getcwd())

# Mock app.config.settings to avoid import errors if config assumes env vars
# We might need to mock app.config before importing app.generator

class MockSettings:
    groq_api_key = "fake_key"
    groq_model = "fake_model"
    groq_timeout_seconds = 10
    
import app.config
app.config.settings = MockSettings()

from app.generator import generate_response
from app.models import CourseSchema

# Mock Groq client
import app.generator
app.generator.Groq = MagicMock()

def test_gen():
    print("Testing generate_response...")
    
    # Dummy Course
    c1 = MagicMock()
    c1.course_id = "111"
    c1.title = "Test Course"
    c1.level = "Beginner"
    c1.category = "Tech"
    c1.instructor = "Tester"
    c1.duration_hours = 5
    c1.skills = "Python"
    c1.description = "Desc"
    
    # Dummy Map (Chat.py creates dicts for entries)
    skill_map = {
        "Python": [
            {"course_id": "111", "title": "Test Course", "level": "Beginner", "instructor": "Tester"}
        ]
    }
    
    try:
        resp = generate_response(
            user_question="I want to learn Python",
            in_scope=True,
            intent="CAREER_GUIDANCE",
            target_categories=["Tech"],
            catalog_results=[c1], # List of objects
            skill_course_map=skill_map,
            ordered_skills=["Python"]
        )
        print("Success!")
        print(json.dumps(resp, indent=2))
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gen()
