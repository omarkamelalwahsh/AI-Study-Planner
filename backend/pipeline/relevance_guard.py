"""
Career Copilot RAG Backend - Step 5: Relevance Guard
Filters out irrelevant results before displaying to user.
"""
import logging
from typing import List, Optional

from models import IntentType, IntentResult, CourseDetail, SkillValidationResult

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
        previous_domains: Optional[set] = None,
    ) -> List[CourseDetail]:
        """
        Filter courses to ensure relevance to user's query.
        
        Args:
            courses: Initial list of retrieved courses
            intent_result: User's intent classification
            skill_result: Validated skills
            user_message: Original user message
            previous_domains: Domains from previous turn for context persistence
            
        Returns:
            Filtered list of relevant courses
        """
        if not courses:
            return []
        
        # Check if user explicitly wants soft skills
        wants_soft_skills = self._wants_soft_skills(user_message)
        
        # Get user's primary domain(s) from skill results
        user_domains = set(skill_result.skill_to_domain.values())
        if previous_domains:
             # Merge with previous domains to allow continuity
             user_domains.update({str(d).lower() for d in previous_domains})
        
        # Merged Intent: Skip strict axes filtering for roadmaps
        guidance_intents = [IntentType.LEARNING_PATH, IntentType.CAREER_GUIDANCE]
        
        filtered = []
        for course in courses:
            # Check relevance using strict V5 rules (Axis Overlap)
            if self._is_relevant(course, user_domains, wants_soft_skills, intent_result, skill_result, user_message):
                 # Additional V5 Relevance Gate: Axis Overlap
                 # If we have V5 search axes, enforce that the course contains at least one axis keyword
                 # NUCLEAR RULE: Skip Axis Overlap for Guidance/Roadmaps as they need breadth
                 if hasattr(intent_result, 'search_axes') and intent_result.search_axes and intent_result.intent not in guidance_intents:
                      overlap_score = self._check_overlap(course, intent_result.search_axes)
                      if overlap_score > 0:
                           filtered.append(course)
                      else:
                           # Strict policy for SEARCH: Discard if no axes match
                           pass
                 else:
                      # No axes or is a Guidance/Roadmap -> Keep if domain matched
                      filtered.append(course)

        # STRICT TOPIC FILTERING (Post-Overlap)
        # If we successfully filtered by domain/overlap, but user asked for "Python", 
        # we must ensure we don't return "JavaScript" even if it passed the "Programming" domain check.
        
        guidance_intents = [IntentType.LEARNING_PATH, IntentType.CAREER_GUIDANCE]
        
        target_topic = intent_result.specific_course or intent_result.slots.get("topic")
        # Only apply if we have a specific target topic and it's not too broad (heuristic: len > 2)
        # NUCLEAR RULE: Do NOT apply strict keyword filter for Guidance/Learning Paths as they are broad
        if target_topic and len(target_topic) > 2 and intent_result.intent not in guidance_intents:
             # But don't filter if topic implies a category (e.g., "programming")
             if target_topic.lower() not in ["programming", "development", "it", "music", "business", "marketing"]:
                  strict_filtered = self._apply_strict_topic_filter(filtered, target_topic)
                  if strict_filtered:
                       filtered = strict_filtered
                  elif hasattr(intent_result, 'search_axes') and intent_result.search_axes:
                       # If strict filter by exact topic failed, maybe the search axes (expanded query) can help?
                       # Or we fall back to the loose filter but with a warning or low score?
                       # For now: if strict filter kills everything, we might fall back to "related" strategy
                       # But user wants STRICT. So let's return [] and trigger fallback response.
                       # However, to be safe against "typos" or "synonyms", maybe we rely on overlap?
                       # User rule: "If user said Python... retrieved must include Python".
                       # So we respect the empty list here.
                       filtered = []

        # If strict filtering removed everything, fallback to original set (to avoid zero results if overlap failed due to strictness)
        if hasattr(intent_result, 'search_axes') and intent_result.search_axes and not filtered and courses and not target_topic:
             logger.warning("V5 Relevance Gate removed all courses. Fallback to weaker relevance check.")
             return courses 

        logger.info(f"Relevance filter: {len(courses)} → {len(filtered)} courses")
        return filtered
    
    def _check_overlap(self, course: CourseDetail, axes: List[str]) -> int:
        """Count how many Search Axes keywords appear in course title/description."""
        text = (str(course.title) + " " + str(course.description) + " " + str(course.category)).lower()
        score = 0
        for axis in axes:
             if axis.lower() in text:
                  score += 1
        return score

    def _apply_strict_topic_filter(self, courses: List[CourseDetail], topic: str) -> List[CourseDetail]:
        """
        User Rule 3: STRICT keyword filter.
        If user said 'Python', course MUST contain 'Python' in title, category, or description.
        """
        topic_lower = topic.lower()
        filtered = []
        for c in courses:
            text_blob = (str(c.title) + " " + str(c.category) + " " + str(c.description)).lower()
            if topic_lower in text_blob:
                filtered.append(c)
            # Special case: 'programming' is too broad, but if topic is 'python', we require python.
            # If topic itself is 'programming', then almost anything tech works.
        
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
        if skill_result and (skill_result.validated_skills or user_domains):
            # Use user_domains which already includes current + previous context
            allowed_domains = {str(d).lower() for d in user_domains}
            
            # Special case for "Programming" and "Data Security" overlap for tech keywords
            tech_keywords = {'python', 'javascript', 'php', 'sql', 'mysql', 'html', 'css', 'programming', 'code', 'database'}
            if any(k in title or k in description for k in tech_keywords):
                allowed_domains.update({'programming', 'data security'})
            
            # If course category is not in allowed domains, it's a cross-domain noise
            # V6 Fix: Allow partial matches (e.g. "Sales Strategy" matches "Sales")
            if category and not any(d in category or category in d for d in allowed_domains):
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
