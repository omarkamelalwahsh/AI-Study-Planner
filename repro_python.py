
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("H:/Career Copilot RAG/backend"))

from data_loader import data_loader
from pipeline.retriever import CourseRetriever
from models import SkillValidationResult

async def test_python():
    print("--- Diagnostic Test: Python Course Retrieval ---")
    
    # 1. Load data
    success = data_loader.load_all()
    if not success:
        print("FAIL: DataLoader could not load files.")
        return
    
    print(f"Data Loaded: {len(data_loader.courses_df)} courses, {len(data_loader.skills_df)} skills")
    
    # 2. Validate skill
    skill = "Python"
    validated = data_loader.validate_skill(skill)
    print(f"Validated Skill '{skill}': {validated}")
    
    # 3. Check skill info
    info = data_loader.get_skill_info(validated) if validated else None
    print(f"Skill Info for '{validated}': {info}")
    
    # 4. Get courses via DataLoader directly
    courses_raw = data_loader.get_courses_for_skill(validated) if validated else []
    print(f"Courses for '{validated}' (Raw): {len(courses_raw)}")
    for c in courses_raw:
        print(f"  - {c.get('title')}")
        
    # 5. Test Retriever
    retriever = CourseRetriever()
    skill_result = SkillValidationResult(
        validated_skills=[validated] if validated else [],
        skill_to_domain={validated: info.get('domain')} if info else {},
        unmatched_terms=[] if validated else [skill]
    )
    
    retrieved = retriever.retrieve(skill_result)
    print(f"Retrieved Courses via CourseRetriever: {len(retrieved)}")
    for c in retrieved:
        print(f"  - {c.title} ({c.level})")

if __name__ == "__main__":
    asyncio.run(test_python())
