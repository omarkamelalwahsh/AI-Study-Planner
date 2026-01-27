
import asyncio
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath("H:/Career Copilot RAG/backend"))

from data_loader import data_loader
from pipeline import (
    IntentRouter,
    SemanticLayer,
    SkillExtractor,
    CourseRetriever,
    RelevanceGuard,
    ResponseBuilder,
)
from llm.groq_client import get_llm_client

async def test_full_pipeline():
    print("--- Full Pipeline Test: Python Retrieval ---")
    
    # Init
    data_loader.load_all()
    llm = get_llm_client()
    intent_router = IntentRouter(llm)
    semantic_layer = SemanticLayer(llm)
    skill_extractor = SkillExtractor()
    retriever = CourseRetriever()
    relevance_guard = RelevanceGuard()
    response_builder = ResponseBuilder(llm)
    
    messages = [
        "عاوز اتعلم بايثون"
    ]
    
    for user_message in messages:
        print(f"\n>>> USER: {user_message}")
        
        # Step 1: Intent
        intent_result = await intent_router.classify(user_message)
        print(f"Intent: {intent_result.intent.value}")
        
        # Step 2: Semantic
        semantic_result = await semantic_layer.analyze(user_message, intent_result)
        
        # Step 3: Skills
        skill_result = skill_extractor.validate_and_filter(semantic_result)
        print(f"Validated Skills: {skill_result.validated_skills}")
        
        # Step 4: Retrieval
        courses = retriever.retrieve(skill_result)
        if intent_result.specific_course:
            courses = retriever.retrieve_by_title(intent_result.specific_course)
        print(f"Retrieved: {len(courses)} courses")
        
        # Step 5: Relevance
        filtered = relevance_guard.filter(courses, intent_result, skill_result, user_message)
        print(f"Filtered: {len(filtered)} courses")
        
        # Step 6: Response
        answer, projects = await response_builder.build(
            intent_result, filtered, skill_result, user_message
        )
        
        print("\n--- RESPONSE ---")
        print(answer)
        if projects:
            print(f"\nProjects Suggested: {len(projects)}")
        print("----------------")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
