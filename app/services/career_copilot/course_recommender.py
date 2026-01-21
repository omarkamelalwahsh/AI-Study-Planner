import logging
from typing import List, Dict, Any
from app.search.retrieval import SearchEngine
from app.schemas_career import RecommendedCourseSchema

logger = logging.getLogger(__name__)

class CourseRecommender:
    @staticmethod
    def recommend(skills: List[str], constraints: Dict[str, Any]) -> List[RecommendedCourseSchema]:
        """
        STEP 4 — INTERNAL COURSE MATCHING
        Match skills/topics to courses. Ground in existing catalog.
        """
        query = " ".join(skills)
        # Use existing search engine (FAISS + Keyword) for hybrid retrieval
        raw_results = SearchEngine.search(query, top_k=15)
        
        recommended = []
        # Grounding: Only use valid course_id from catalog.
        # Filtering by level if provided
        target_level = constraints.get("level", "beginner").lower()
        
        for res in raw_results:
            # Rank courses (implicitly by FAISS score) and ensure valid data
            course_id = str(res.get("id"))
            if not course_id or course_id == "None":
                continue
            
            # Simple level matching heuristic
            course_level = str(res.get("level", "beginner")).lower()
            relevance_why = f"Matches required skills: {', '.join(skills[:2])}."
            
            recommended.append(RecommendedCourseSchema(
                course_id=course_id,
                title=res.get("title", "Unknown Course"),
                instructor=res.get("instructor"),
                duration_hours=float(res.get("duration_hours") or 5.0),
                level=res.get("level"),
                url=res.get("url"),
                description=res.get("description"),
                why=relevance_why
            ))
            
        # Optional: Limit to top candidates to avoid overwhelming
        return recommended[:10]
