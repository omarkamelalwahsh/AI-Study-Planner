"""
Career Copilot RAG Backend - Step 5: Relevance Guard
Filters out irrelevant results before displaying to user.
"""
import logging
from typing import List, Optional

from models import IntentResult, CourseDetail, SkillValidationResult

logger = logging.getLogger(__name__)


class RelevanceGuard:
    """
    Step 5: Filter irrelevant courses before response.
    
    CRITICAL QUESTION: "Does this serve the user's question directly?"
    
    Rules:
    1. Remove courses unrelated to user's domain/intent
    2. Remove generic soft skills unless explicitly requested
    3. Apply domain-based filtering
    """
    
    # Categories considered "generic soft skills"
    SOFT_SKILL_CATEGORIES = {
        'soft skills',
        'personal development',
        'general',
        'health & wellness',
    }
    
    # Keywords that indicate user wants soft skills
    SOFT_SKILL_INDICATORS = {
        'soft skills', 'مهارات ناعمة', 'communication', 'تواصل',
        'leadership', 'قيادة', 'personal development', 'تطوير ذاتي',
    }
    
    def filter(
        self,
        courses: List[CourseDetail],
        intent_result: IntentResult,
        skill_result: SkillValidationResult,
        user_message: str,
    ) -> List[CourseDetail]:
        """
        Filter courses to ensure relevance to user's query.
        
        Args:
            courses: Initial list of retrieved courses
            intent_result: User's intent classification
            skill_result: Validated skills
            user_message: Original user message
            
        Returns:
            Filtered list of relevant courses
        """
        if not courses:
            return []
        
        # Check if user explicitly wants soft skills
        wants_soft_skills = self._wants_soft_skills(user_message)
        
        # Get user's primary domain(s) from skill results
        user_domains = set(skill_result.skill_to_domain.values())
        
        filtered = []
        for course in courses:
            # Check relevance
            if self._is_relevant(course, user_domains, wants_soft_skills, intent_result, skill_result, user_message):
                filtered.append(course)
        
        logger.info(f"Relevance filter: {len(courses)} → {len(filtered)} courses")
        return filtered
    
    def _is_relevant(
        self,
        course: CourseDetail,
        user_domains: set,
        wants_soft_skills: bool,
        intent_result: IntentResult,
        skill_result: SkillValidationResult = None,
        user_message: str = "",
    ) -> bool:
        """Check if a single course is relevant."""
        category = str(course.category or '').lower()
        title = str(course.title or '').lower()
        description = str(course.description or '').lower()
        
        # If no skills were validated, be VERY strict with any course retrieved
        if skill_result and not skill_result.validated_skills and skill_result.unmatched_terms:
            # Check if course title/description has ANY overlap with the unmatched terms
            for term in skill_result.unmatched_terms:
                term_lower = term.lower()
                if term_lower in title or term_lower in description:
                    return True
            
            # If no keyword overlap and no validated skills, this is probably a cross-domain hallucination from retrieval/semantic
            return False

        # Domain Safety Check (Crucial for grounding)
        if skill_result and skill_result.validated_skills:
            # Get domains from validated skills
            allowed_domains = {str(d).lower() for d in skill_result.skill_to_domain.values()}
            
            # Special case for "Programming" and "Data Security" overlap for tech keywords
            tech_keywords = {'python', 'javascript', 'php', 'sql', 'mysql', 'html', 'css', 'programming', 'code'}
            if any(k in title or k in description for k in tech_keywords):
                allowed_domains.update({'programming', 'data security'})
            
            # If course category is not in allowed domains, it's a cross-domain noise
            if category and category not in allowed_domains:
                # If it's a soft skill and not requested, we already filter below, 
                # but this also catches other unrelated domains (e.g., Banking, Public Speaking)
                return False

        # If user explicitly wants soft skills, don't filter them out
        if wants_soft_skills:
            return True
        
        # If course is soft skills and user didn't ask for them, filter out
        if category in self.SOFT_SKILL_CATEGORIES:
            # If user has a specific technical domain, soft skills are probably noise
            if user_domains and not any(d.lower() in self.SOFT_SKILL_CATEGORIES for d in user_domains):
                return False
        
        return True
    
    def _wants_soft_skills(self, message: str) -> bool:
        """Check if user explicitly wants soft skills."""
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in self.SOFT_SKILL_INDICATORS)
    
    def limit_results(
        self,
        courses: List[CourseDetail],
        max_courses: int = 10,
    ) -> List[CourseDetail]:
        """
        Apply display limit to courses.
        Note: We return all for retrieval but may limit for display.
        """
        return courses[:max_courses]
