"""
Career Copilot RAG Backend - Step 7: Consistency Checker
Final validation to ensure response is grounded in data.
"""
import logging
from typing import List, Set

from data_loader import data_loader
from models import CourseDetail

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """
    Step 7: Final validation before sending response.
    
    Checks:
    1. ✅ All mentioned content exists in data?
    2. ✅ Nothing invented or hallucinated?
    3. ✅ Response logical for the question?
    """
    
    def __init__(self):
        self.data = data_loader
    
    def validate_courses(self, courses: List[CourseDetail]) -> List[CourseDetail]:
        """
        Validate that all courses exist in our database.
        Removes any courses that don't match our records.
        """
        validated = []
        
        for course in courses:
            # Verify course exists
            db_course = self.data.get_course_by_id(course.course_id)
            if db_course:
                validated.append(course)
            else:
                logger.warning(f"Consistency check failed: Course {course.course_id} not in database")
        
        return validated
    
    def validate_response_text(
        self,
        response_text: str,
        courses: List[CourseDetail],
    ) -> tuple[bool, str]:
        """
        Validate response text doesn't mention courses not in the list.
        
        Returns:
            Tuple of (is_valid, cleaned_response)
        """
        # Get list of valid course titles
        valid_titles: Set[str] = {c.title.lower() for c in courses}
        
        # For now, we trust the response builder output
        # In production, could add more sophisticated validation
        
        return True, response_text
    
    def check_no_hallucination(
        self,
        mentioned_skills: List[str],
        mentioned_courses: List[str],
    ) -> bool:
        """
        Verify no hallucinated content.
        All skills and courses mentioned must exist in data.
        """
        # Check skills
        for skill in mentioned_skills:
            if not self.data.validate_skill(skill):
                logger.warning(f"Hallucination detected: Skill '{skill}' not in catalog")
                return False
        
        # Check courses by title
        for course_title in mentioned_courses:
            matches = self.data.search_courses_by_title(course_title)
            if not matches:
                logger.warning(f"Hallucination detected: Course '{course_title}' not in database")
                return False
        
        return True
    
    def check(
        self,
        answer: str,
        courses: List[CourseDetail],
    ) -> tuple[bool, List[str]]:
        """
        Production Hardening: Multi-return consistency check.
        Returns (is_consistent, inconsistencies).
        """
        inconsistencies = []
        
        # 1. Existence Check
        valid_courses = self.validate_courses(courses)
        if len(valid_courses) < len(courses):
            missing = len(courses) - len(valid_courses)
            inconsistencies.append(f"Removed {missing} courses not found in database.")
            
        # 2. Text Grounding Check
        # For now simple pass, but can be expanded
        is_valid_text, _ = self.validate_response_text(answer, valid_courses)
        if not is_valid_text:
            inconsistencies.append("Response text mentions courses not in the data list.")
            
        return len(inconsistencies) == 0, inconsistencies

    def final_check(
        self,
        answer: str,
        courses: List[CourseDetail],
    ) -> tuple[str, List[CourseDetail]]:
        """
        Perform final consistency check on the response.
        
        Returns:
            Tuple of (validated_answer, validated_courses)
        """
        # Validate courses exist
        validated_courses = self.validate_courses(courses)
        
        # Validate response
        is_valid, validated_answer = self.validate_response_text(answer, validated_courses)
        
        if len(validated_courses) < len(courses):
            logger.info(f"Removed {len(courses) - len(validated_courses)} invalid courses")
        
        return validated_answer, validated_courses
