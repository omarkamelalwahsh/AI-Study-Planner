"""
Career Copilot RAG Backend - Step 4: Course Retriever
Retrieves courses based on validated skills from the index.
"""
import logging
from typing import List, Dict, Optional
from collections import defaultdict

from data_loader import data_loader
from models import CourseDetail, SkillValidationResult

logger = logging.getLogger(__name__)


class CourseRetriever:
    """
    Step 4: Retrieve courses from skill-to-courses index.
    
    CRITICAL RULES:
    1. No arbitrary limits - return all matching courses
    2. Order by relevance (number of matching skills)
    3. Then order by level (Beginner → Intermediate → Advanced)
    """
    
    LEVEL_ORDER = {
        'beginner': 0,
        'intermediate': 1,
        'advanced': 2,
    }
    
    def __init__(self):
        self.data = data_loader
    
    def retrieve(
        self,
        skill_result: SkillValidationResult,
        level_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[CourseDetail]:
        """
        Retrieve courses for validated skills.
        
        Args:
            skill_result: Validated skills from skill extractor
            level_filter: Optional filter by course level
            category_filter: Optional filter by category
            
        Returns:
            List of CourseDetail ordered by relevance
        """
        skills = skill_result.validated_skills
        unmatched = skill_result.unmatched_terms
        
        if not skills and not unmatched:
            logger.info("No skills or unmatched terms to search for")
            return []
        
        # Collect courses and count skill matches
        course_scores: Dict[str, int] = defaultdict(int)
        course_data: Dict[str, dict] = {}
        
        # Tier 2: Skill matching (from index)
        for skill in skills:
            courses = self.data.get_courses_for_skill(skill)
            for course in courses:
                course_id = course.get('course_id')
                if course_id:
                    course_scores[course_id] += 1
                    course_data[course_id] = course
        
        # Tier 1: Direct title-based matching for keywords (especially if skills found are sparse)
        # We look at validated skills AND unmatched terms that look like keywords
        search_terms = set(skills) | set(skill_result.unmatched_terms)
        for term in search_terms:
            if len(term) < 3: continue # Skip short terms
            
            title_matches = self.data.search_courses_by_title(term)
            for course in title_matches:
                course_id = course.get('course_id')
                if course_id:
                    # Tier 1 match gets a boost + more weight than skill match
                    course_scores[course_id] += 2 
                    course_data[course_id] = course
        
        if not course_data:
            logger.info(f"No courses found for skills: {skills}")
            return []
        
        # Build result list
        results = []
        for course_id, course in course_data.items():
            # Apply filters
            if level_filter:
                course_level = str(course.get('level', '')).lower()
                if level_filter.lower() not in course_level:
                    continue
            
            if category_filter:
                course_category = str(course.get('category', '')).lower()
                if category_filter.lower() not in course_category:
                    continue
            
            # Get full course details if available
            full_course = self.data.get_course_by_id(course_id) or course
            
            results.append(CourseDetail(
                course_id=course_id,
                title=full_course.get('title', course.get('title', '')),
                category=full_course.get('category', course.get('category')),
                level=full_course.get('level', course.get('level')),
                instructor=full_course.get('instructor', course.get('instructor')),
                duration_hours=full_course.get('duration_hours'),
                description=full_course.get('description'),
            ))
        
        # Sort by relevance (skill match count) then by level
        results.sort(key=lambda c: (
            -course_scores.get(c.course_id, 0),  # Higher score first
            self.LEVEL_ORDER.get(str(c.level).lower(), 1),  # Beginner first
        ))
        
        logger.info(f"Retrieved {len(results)} courses for {len(skills)} skills")
        return results
    
    def retrieve_by_title(self, title_query: str) -> List[CourseDetail]:
        """
        Search courses by title for specific course queries.
        """
        courses = self.data.search_courses_by_title(title_query)
        
        results = []
        for course in courses:
            results.append(CourseDetail(
                course_id=course.get('course_id', ''),
                title=course.get('title', ''),
                category=course.get('category'),
                level=course.get('level'),
                instructor=course.get('instructor'),
                duration_hours=course.get('duration_hours'),
                description=course.get('description'),
            ))
        
        return results
    
    def get_course_details(self, course_id: str) -> Optional[CourseDetail]:
        """
        Get detailed information about a specific course.
        """
        course = self.data.get_course_by_id(course_id)
        if not course:
            return None
        
        return CourseDetail(
            course_id=course.get('course_id', course_id),
            title=course.get('title', ''),
            category=course.get('category'),
            level=course.get('level'),
            instructor=course.get('instructor'),
            duration_hours=course.get('duration_hours'),
            description=course.get('description'),
        )
    
    def get_all_categories(self) -> List[str]:
        """Get all available course categories for browsing."""
        return self.data.get_all_categories()
    
    def browse_all(self, limit: int = 50) -> List[CourseDetail]:
        """
        Get all courses for catalog browsing.
        Returns a sample of courses from each category.
        """
        if self.data.courses_df is None:
            return []
        
        results = []
        df = self.data.courses_df
        
        # Get sample from each category to show variety
        categories = df['category'].dropna().unique().tolist()
        per_category = max(2, limit // len(categories)) if categories else limit
        
        for category in categories:
            category_courses = df[df['category'] == category].head(per_category)
            for _, course in category_courses.iterrows():
                results.append(CourseDetail(
                    course_id=course.get('course_id', ''),
                    title=course.get('title', ''),
                    category=course.get('category'),
                    level=course.get('level'),
                    instructor=course.get('instructor'),
                    duration_hours=course.get('duration_hours'),
                    description=course.get('description'),
                ))
        
        return results[:limit]
    
    def browse_by_category(self, category: str, limit: int = 20) -> List[CourseDetail]:
        """Get courses in a specific category."""
        if self.data.courses_df is None:
            return []
        
        df = self.data.courses_df
        matches = df[df['category'].str.lower().str.contains(category.lower(), na=False)]
        
        results = []
        for _, course in matches.head(limit).iterrows():
            results.append(CourseDetail(
                course_id=course.get('course_id', ''),
                title=course.get('title', ''),
                category=course.get('category'),
                level=course.get('level'),
                instructor=course.get('instructor'),
                duration_hours=course.get('duration_hours'),
                description=course.get('description'),
            ))
        
        return results
    
    def get_categories_with_counts(self) -> Dict[str, int]:
        """Get categories with course counts."""
        if self.data.courses_df is None:
            return {}
        
        return self.data.courses_df['category'].value_counts().to_dict()

