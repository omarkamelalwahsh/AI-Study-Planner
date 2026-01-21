import logging
import re
import difflib
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Course
from app.search.embedding import normalize_ar, is_generic_opinion_query
from app.search.retrieval import SearchEngine
from app.search.query_parser import (
    ParsedQuery,
    parse_query_basic,
    INTENT_CATEGORY,
    INTENT_EXACT_COURSE,
    INTENT_TOPIC,
    INTENT_NO_MATCH,
)
from app.search.relevance import (
    apply_strict_filters,
    apply_level_filter,
    group_by_level,
    normalize_level,
    parse_explicit_level,
    is_generic_query,
)

logger = logging.getLogger(__name__)

# ---------------------------
# Configuration
# ---------------------------
TITLE_FUZZY_THRESHOLD = 0.85  # Fuzzy matching for titles
CATEGORY_FUZZY_THRESHOLD = 0.85  # Fuzzy matching for categories

# ---------------------------
# ULTRA-STRICT 3-TIER ROUTER
# ---------------------------

def _norm_strict(s: str) -> str:
    """Strict normalization for exact matching."""
    s = normalize_ar(s or "")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _best_fuzzy_match(query: str, choices: List[str], threshold: float) -> Optional[str]:
    """Find best fuzzy match with support for partials and variations."""
    q_norm = _norm_strict(query)
    if not q_norm or not choices:
        return None
    
    # Handle common variations like 3d -> 3 d
    q_alt = q_norm.replace("3d", "3 d") if "3d" in q_norm else q_norm
    
    best_match = None
    best_ratio = 0.0
    
    for choice in choices:
        c_norm = _norm_strict(choice)
        if not c_norm: continue
        
        # 1. Exact or starts-with (Priority)
        if q_norm == c_norm or c_norm.startswith(q_norm) or q_alt == c_norm or c_norm.startswith(q_alt):
            return choice
            
        # 2. Fuzzy match
        ratio = difflib.SequenceMatcher(None, q_norm, c_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = choice
    
    if best_ratio >= threshold:
        return best_match
    return None

class SearchRouter:
    @staticmethod
    def route_query(query: str) -> dict:
        """
        ULTRA-STRICT 3-TIER SEARCH ROUTER
        
        Routing Order (STOP at first match):
        1. Title Route - Exact/fuzzy course title matching
        2. Category Route - Exact category matching  
        3. Semantic Route - FAISS embedding search with strict filters
        
        If query is generic without subject -> no_match immediately
        """
        db = SessionLocal()
        try:
            # ---------------------------
            # 0) PREPROCESSING
            # ---------------------------
            query_normalized = normalize_ar(query)
            
            # Parse level from query (None if not mentioned)
            level = parse_explicit_level(query_normalized)
            level_mode = "single_level" if level else "all_levels"
            
            logger.info(f"Query: '{query}' | Normalized: '{query_normalized}' | Level: {level}")
            
            # ---------------------------
            # 0.5) GENERIC QUERY GUARD
            # ---------------------------
            # Block queries without subject (e.g., "recommend", "Is this good?")
            if is_generic_query(query_normalized):
                logger.info(f"Generic query blocked: '{query}'")
                return SearchRouter._format_no_match(
                    query,
                    "Generic query without specific subject",
                    "generic_no_subject"
                )
            
            # Also check opinion queries
            if is_generic_opinion_query(query_normalized):
                logger.info(f"Opinion query blocked: '{query}'")
                return SearchRouter._format_no_match(
                    query,
                    "Opinion/recommendation query without specific subject",
                    "opinion_no_subject"
                )
            
            # ---------------------------
            # 1) TITLE ROUTE (Highest Priority)
            # ---------------------------
            all_courses = db.query(Course).all()
            all_titles = [c.title for c in all_courses if c.title]
            
            matched_title = _best_fuzzy_match(query_normalized, all_titles, TITLE_FUZZY_THRESHOLD)
            
            if matched_title:
                logger.info(f"ROUTE: Title | Matched: '{matched_title}'")
                return SearchRouter._return_title_match(db, matched_title, level, level_mode)
            
            # ---------------------------
            # 2) CATEGORY ROUTE (Second Priority)
            # ---------------------------
            all_categories = list(set(c.category for c in all_courses if c.category))
            
            matched_category = _best_fuzzy_match(query_normalized, all_categories, CATEGORY_FUZZY_THRESHOLD)
            
            if matched_category:
                logger.info(f"ROUTE: Category | Matched: '{matched_category}'")
                return SearchRouter._return_category_match(db, matched_category, level, level_mode)
            
            # ---------------------------
            # 3) SEMANTIC ROUTE (Fallback)
            # ---------------------------
            logger.info(f"ROUTE: Semantic (FAISS)")
            
            # Retrieve top 30 from FAISS
            raw_candidates = SearchEngine.search(query_normalized, top_k=30) or []
            
            if not raw_candidates:
                return SearchRouter._format_no_match(
                    query,
                    "No courses found in semantic search",
                    "semantic_empty"
                )
            
            # Apply ULTRA-STRICT filters (band + keyword overlap + max 5)
            filtered = apply_strict_filters(query_normalized, raw_candidates)
            
            if not filtered:
                return SearchRouter._format_no_match(
                    query,
                    "No courses passed strict filtering (band/keyword overlap)",
                    "semantic_filtered_empty"
                )
            
            # Apply level filter with fallback
            final_results, final_level_mode = apply_level_filter(filtered, level)
            
            # Build message
            if final_level_mode == "fallback_all_levels":
                message = f"لم نجد نتائج للمستوى {level}، إليك جميع المستويات / No results for level {level}, showing all levels"
            elif final_level_mode == "level_filtered":
                message = f"Found {len(final_results)} courses for level: {level}"
            else:
                message = f"Found {len(final_results)} courses"
            
            return SearchRouter._format_response(
                status="ok",
                route="semantic",
                message=message,
                level_mode=final_level_mode,
                results=final_results
            )
            
        finally:
            db.close()
    
    # ---------------------------
    # Response Builders
    # ---------------------------
    
    @staticmethod
    def _return_title_match(db: Session, title: str, level: Optional[str], level_mode: str) -> dict:
        """Return results for exact title match."""
        courses = db.query(Course).filter(Course.title == title).all()
        
        if not courses:
            # Fallback to case-insensitive
            courses = db.query(Course).filter(Course.title.ilike(title)).all()
        
        if not courses:
            return SearchRouter._format_no_match(title, "Title found but no courses in DB", "db_sync_error")
        
        # Convert to candidates
        results = SearchRouter._to_candidates(courses)
        
        # Apply level filter
        final_results, final_level_mode = apply_level_filter(results, level)
        
        message = f"Exact match: {title}"
        if final_level_mode == "fallback_all_levels":
            message += f" | Level {level} not available, showing all levels"
        
        return SearchRouter._format_response(
            status="ok",
            route="title",
            message=message,
            level_mode=final_level_mode,
            results=final_results
        )
    
    @staticmethod
    def _return_category_match(db: Session, category: str, level: Optional[str], level_mode: str) -> dict:
        """Return all courses in matched category."""
        courses = db.query(Course).filter(Course.category == category).all()
        
        if not courses:
            return SearchRouter._format_no_match(category, "Category found but no courses", "db_empty_category")
        
        # Convert to candidates
        results = SearchRouter._to_candidates(courses)
        
        # Apply level filter
        final_results, final_level_mode = apply_level_filter(results, level)
        
        message = f"Category: {category}"
        if final_level_mode == "fallback_all_levels":
            message += f" | Level {level} not available, showing all levels"
        
        return SearchRouter._format_response(
            status="ok",
            route="category",
            message=message,
            level_mode=final_level_mode,
            results=final_results
        )
    
    @staticmethod
    def _to_candidates(courses: List[Course]) -> List[dict]:
        """Convert DB Course objects to candidate dicts."""
        return [
            {
                "id": str(c.id),
                "title": c.title,
                "description": c.description,
                "category": c.category,
                "level": c.level,
                "duration_hours": getattr(c, "duration_hours", None),
                "skills": getattr(c, "skills", None),
                "score": 1.0,  # Perfect match for DB-only routes
                "url": getattr(c, "url", None),
            }
            for c in courses
        ]
    
    @staticmethod
    def _format_response(status: str, route: str, message: str, level_mode: str, results: list) -> dict:
        """Format successful response with results grouped by level."""
        results_by_level = group_by_level(results)
        
        return {
            "status": status,
            "route": route,
            "message": message,
            "level_mode": level_mode,
            "results_by_level": results_by_level,
        }
    
    @staticmethod
    def _format_no_match(query: str, message: str, reason_code: str) -> dict:
        """Format no-match response."""
        return {
            "status": "no_match",
            "route": "no_match",
            "message": message,
            "level_mode": "all_levels",
            "results_by_level": {
                "Beginner": [],
                "Intermediate": [],
                "Advanced": [],
            },
            "debug_reason": reason_code,
        }
