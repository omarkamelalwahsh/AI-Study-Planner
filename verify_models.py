import asyncio
import logging
import os
import sys

# Add current dir to sys.path
sys.path.append(os.getcwd())

from app.llm.groq_client import reasoning_model, copilot_model
# genai removed
from app.router import classify_intent_strict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verification")

def list_available_models():
    print("--- Listing Available Models (Groq) ---")
    print("Using Groq Model defined in settings.")

def test_router_sync():
    print("\n--- Testing Router (Reasoning Model) ---")
    queries = [
        "manager sales",
        "عايز أتعلم برمجة"
    ]
    for q in queries:
        try:
            print(f"Query: {q}")
            output = classify_intent_strict(q)
            print(f"Result JSON: {output}")
        except Exception as e:
            print(f"Router Error: {e}")

def test_copilot_sync():
    print("\n--- Testing Copilot (Production Model) ---")
    context = """
CONTEXT:
User Request: I want to be a Data Scientist
Extracted Domain: Data Science
Retrieved Courses (Top Relevance):
[
  {"title": "Data Science 101", "level": "Beginner", "category": "Data", "skills": ["Python", "Pandas"]},
  {"title": "Advanced Machine Learning", "level": "Advanced", "category": "Data", "skills": ["TensorFlow", "Math"]}
]

TASK:
Generate a response following "Format B) CAREER GUIDANCE" strictly.
"""
    try:
        response = copilot_model.generate_content(context)
        print("Copilot Response:\n" + response.text)
    except Exception as e:
        print(f"Copilot Error: {e}")

if __name__ == "__main__":
    list_available_models()
    test_router_sync()
    test_copilot_sync()
