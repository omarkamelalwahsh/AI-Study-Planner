import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AssessmentService:
    @staticmethod
    def get_assessment_questions(field: str, level: str = "beginner") -> List[Dict[str, Any]]:
        """
        STEP 7 — OPTIONAL LEVEL ASSESSMENT
        Get 5-8 short questions based on field and current level.
        """
        # Placeholder questions
        questions = [
            {"id": "q1", "text": "How many years of experience do you have in this field?", "options": ["0-1", "2-4", "5+"]},
            {"id": "q2", "text": "Are you familiar with the basic concepts of this role?", "options": ["Yes", "Somewhat", "No"]},
            {"id": "q3", "text": "Have you used tools like X or Y before?", "options": ["Yes", "A little", "Never"]},
            {"id": "q4", "text": "What is your main goal for this learning journey?", "options": ["Career switch", "Upskilling", "Curiosity"]},
            {"id": "q5", "text": "How much time can you commit daily?", "options": ["< 1 hour", "1-2 hours", "3+ hours"]}
        ]
        return questions

    @staticmethod
    def evaluate_level(answers: Dict[str, str]) -> str:
        """
        Evaluate level based on answers.
        """
        # Simple evaluation logic
        score = len(answers) # Dummy score
        if score > 4:
            return "intermediate"
        elif score > 6:
            return "advanced"
        return "beginner"
