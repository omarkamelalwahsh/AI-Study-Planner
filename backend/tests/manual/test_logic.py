
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("H:/Career Copilot RAG/backend"))

from data_loader import data_loader
from pipeline import CourseRetriever, RelevanceGuard
from models import SkillValidationResult, IntentResult, IntentType

async def test_logic():
    print("--- Local Logic Test (No LLM) ---")
    data_loader.load_all()
    
    retriever = CourseRetriever()
    guard = RelevanceGuard()
    
    # CASE 1: User says "بايثون" but LLM extracted "using python"
    # validated_skills=['using python'], unmatched_terms=['بايثون']
    skill_result = SkillValidationResult(
        validated_skills=['using python'],
        skill_to_domain={'using python': 'Data Security'},
        unmatched_terms=['بايثون']
    )
    intent = IntentResult(intent=IntentType.COURSE_SEARCH)
    
    courses = retriever.retrieve(skill_result)
    print(f"\nScenario: 'بايثون' in unmatched, 'using python' in validated")
    print(f"Retrieved: {len(courses)} courses")
    for c in courses:
        print(f"  - {c.title} ({c.category})")
        
    filtered = guard.filter(courses, intent, skill_result, "عاوز اتعلم بايثون")
    print(f"Filtered: {len(filtered)} courses")
    for c in filtered:
        print(f"  - {c.title} ({c.category})")

    # CASE 2: No validated skills, only keyword in unmatched
    skill_result_2 = SkillValidationResult(
        validated_skills=[],
        skill_to_domain={},
        unmatched_terms=['Python']
    )
    courses_2 = retriever.retrieve(skill_result_2)
    print(f"\nScenario: Only 'Python' in unmatched")
    print(f"Retrieved: {len(courses_2)} courses")
    for c in courses_2:
        print(f"  - {c.title} ({c.category})")
        
    filtered_2 = guard.filter(courses_2, intent, skill_result_2, "بايثون")
    print(f"Filtered: {len(filtered_2)} courses")

if __name__ == "__main__":
    asyncio.run(test_logic())
