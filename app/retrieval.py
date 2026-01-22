"""
Retrieval engine for course search (exact match + semantic search).
Implements strict retrieval gates based on intent.
"""
import faiss
import pickle
import numpy as np
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer
from fuzzywuzzy import fuzz
from app.models import Course, CourseSchema
from app.config import settings
import logging
import os

logger = logging.getLogger(__name__)

# Global embedding model and FAISS index (loaded on startup)
_embed_model: Optional[SentenceTransformer] = None
_faiss_index: Optional[faiss.Index] = None
_course_id_mapping: Optional[List[str]] = None  # Maps FAISS index to course_id


def load_vector_store():
    """Load embedding model and FAISS index on startup."""
    global _embed_model, _faiss_index, _course_id_mapping
    
    try:
        # Load embedding model
        logger.info(f"Loading embedding model: {settings.embed_model_name}")
        _embed_model = SentenceTransformer(settings.embed_model_name)
        
        # Load FAISS index - files are in data/faiss_index/index.faiss/
        base_path = settings.faiss_index_path  # "data/faiss_index"
        index_file = os.path.join(base_path, "index.faiss", "courses.faiss")
        mapping_file = os.path.join(base_path, "index.faiss", "id_mapping.pkl")
        
        if os.path.exists(index_file) and os.path.exists(mapping_file):
            logger.info(f"Loading FAISS index from: {index_file}")
            _faiss_index = faiss.read_index(index_file)
            
            with open(mapping_file, "rb") as f:
                _course_id_mapping = pickle.load(f)
            
            logger.info(f"✓ FAISS index loaded: {_faiss_index.ntotal} vectors")
        else:
            logger.warning(f"FAISS index not found at {index_file}. Existing: index={os.path.exists(index_file)}, mapping={os.path.exists(mapping_file)}")
            _faiss_index = None
            _course_id_mapping = None
            
    except Exception as e:
        logger.error(f"Failed to load vector store: {e}")
        _embed_model = None
        _faiss_index = None
        _course_id_mapping = None


async def retrieve_by_exact_title(
    db: AsyncSession,
    title: str,
    fuzzy_threshold: int = None
) -> Tuple[Optional[CourseSchema], List[str]]:
    """
    Retrieve course by exact or fuzzy title match.
    
    Args:
        db: Database session
        title: Course title to search
        fuzzy_threshold: Fuzzy match threshold (default from settings)
        
    Returns:
        (matched_course or None, list of similar titles if not found)
    """
    threshold = fuzzy_threshold or settings.fuzzy_match_threshold
    
    # Try exact match (case insensitive)
    stmt = select(Course).where(func.lower(Course.title) == title.lower())
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    
    if course:
        logger.info(f"Exact title match found: {course.title}")
        return CourseSchema.from_orm(course), []
    
    # Try fuzzy match
    stmt = select(Course)
    result = await db.execute(stmt)
    all_courses = result.scalars().all()
    
    # Calculate fuzzy scores
    matches = []
    for course in all_courses:
        score = fuzz.ratio(title.lower(), course.title.lower())
        if score >= threshold:
            matches.append((course, score))
    
    # Sort by score (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    if matches and matches[0][1] >= threshold:
        best_match = matches[0][0]
        logger.info(f"Fuzzy title match found: {best_match.title} (score: {matches[0][1]})")
        return CourseSchema.from_orm(best_match), []
    
    # No match - return top 3 similar titles
    similar_titles = [course.title for course, score in matches[:3]]
    logger.info(f"No match for '{title}'. Similar titles: {similar_titles}")
    return None, similar_titles


async def retrieve_by_semantic(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    filters: Optional[dict] = None
) -> List[CourseSchema]:
    """
    Retrieve courses using semantic search (FAISS).
    
    Args:
        db: Database session
        query: Search query
        top_k: Number of results to return
        filters: Optional filters (level, category)
        
    Returns:
        List of retrieved courses
    """
    if not _embed_model or not _faiss_index or not _course_id_mapping:
        logger.warning("Vector store not loaded. Falling back to keyword search.")
        return await _fallback_keyword_search(db, query, top_k, filters)
    
    # Generate query embedding
    query_embedding = _embed_model.encode([query])[0]
    query_embedding = np.array([query_embedding], dtype=np.float32)
    
    # FAISS search
    distances, indices = _faiss_index.search(query_embedding, min(top_k * 2, len(_course_id_mapping)))
    
    # Get course IDs
    retrieved_ids = [_course_id_mapping[idx] for idx in indices[0] if idx < len(_course_id_mapping)]
    
    # Fetch courses from database
    stmt = select(Course).where(Course.course_id.in_(retrieved_ids))
    
    # Apply filters
    if filters:
        if filters.get("level"):
            stmt = stmt.where(func.lower(Course.level) == filters["level"].lower())
        if filters.get("category"):
            stmt = stmt.where(func.lower(Course.category) == filters["category"].lower())
    
    result = await db.execute(stmt)
    courses = result.scalars().all()
    
    # Preserve FAISS ranking order
    course_dict = {str(c.course_id): c for c in courses}
    ordered_courses = [course_dict[cid] for cid in retrieved_ids if cid in course_dict]
    
    # Limit to top_k
    ordered_courses = ordered_courses[:top_k]
    
    logger.info(f"Semantic search returned {len(ordered_courses)} courses")
    return [CourseSchema.from_orm(c) for c in ordered_courses]


async def _fallback_keyword_search(
    db: AsyncSession,
    query: str,
    top_k: int,
    filters: Optional[dict] = None
) -> List[CourseSchema]:
    """Fallback to PostgreSQL full-text search if FAISS not available."""
    stmt = select(Course).where(
        func.to_tsvector('english', func.coalesce(Course.title, '') + ' ' + func.coalesce(Course.description, ''))
        .op('@@')(func.plainto_tsquery('english', query))
    )
    
    # Apply filters
    if filters:
        if filters.get("level"):
            stmt = stmt.where(func.lower(Course.level) == filters["level"].lower())
        if filters.get("category"):
            stmt = stmt.where(func.lower(Course.category) == filters["category"].lower())
    
    stmt = stmt.limit(top_k)
    result = await db.execute(stmt)
    courses = result.scalars().all()
    
    logger.info(f"Keyword search (fallback) returned {len(courses)} courses")
    return [CourseSchema.from_orm(c) for c in courses]


async def suggest_similar_titles(db: AsyncSession, title: str, top_k: int = 3) -> List[str]:
    """Get similar course titles for suggestions."""
    stmt = select(Course.title)
    result = await db.execute(stmt)
    all_titles = [row[0] for row in result.all()]
    
    # Calculate fuzzy scores
    scores = [(t, fuzz.ratio(title.lower(), t.lower())) for t in all_titles]
    scores.sort(key=lambda x: x[1], reverse=True)
    
    return [t for t, score in scores[:top_k]]
