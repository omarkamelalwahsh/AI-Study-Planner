"""
retrieval.py
Production-grade retrieval engine for Career Copilot courses:
- Exact/fuzzy title match
- Semantic retrieval via FAISS (SentenceTransformers)
- Robust multilingual fallback search for Arabic/English/mixed queries
"""

from __future__ import annotations

import os
import re
import uuid
import pickle
import logging
from typing import List, Optional, Tuple, Dict, Any

import numpy as np
import faiss

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sentence_transformers import SentenceTransformer
from fuzzywuzzy import fuzz

from app.models import Course, CourseSchema
from app.config import settings

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Globals (loaded on startup)
# -------------------------------------------------------------------
_embed_model: Optional[SentenceTransformer] = None
_faiss_index: Optional[faiss.Index] = None
_course_id_mapping: Optional[List[str]] = None  # list[str] UUIDs in same order as FAISS vectors


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

def _contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))

def _normalize_text(s: str) -> str:
    return (s or "").strip()

def _safe_uuid(val: Any) -> Optional[uuid.UUID]:
    try:
        if val is None:
            return None
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))
    except Exception:
        return None

def _e5_query(text: str) -> str:
    # E5 expects "query: " prefix for queries (recommended)
    return f"query: {text}"

def _e5_passage(text: str) -> str:
    # Use when building index; here for completeness
    return f"passage: {text}"

def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    # vecs shape: (n, d)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms


# -------------------------------------------------------------------
# Vector store loading
# -------------------------------------------------------------------
def _resolve_faiss_paths(base: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Accepts either:
    - a directory path (recommended), or
    - a file path to a .faiss index

    We try common layouts:
    A) <base>/index.faiss/courses.faiss + <base>/index.faiss/id_mapping.pkl
    B) <base>/courses.faiss + <base>/id_mapping.pkl
    C) <base> itself is a .faiss file, and mapping near it
    """
    if not base:
        return None, None

    base = os.path.normpath(base)

    # Case C: base is a file
    if os.path.isfile(base) and base.lower().endswith(".faiss"):
        idx_file = base
        mapping_file = os.path.join(os.path.dirname(base), "id_mapping.pkl")
        return idx_file, mapping_file if os.path.exists(mapping_file) else mapping_file

    # Case A
    idx_a = os.path.join(base, "index.faiss", "courses.faiss")
    map_a = os.path.join(base, "index.faiss", "id_mapping.pkl")
    if os.path.exists(idx_a) and os.path.exists(map_a):
        return idx_a, map_a

    # Case B
    idx_b = os.path.join(base, "courses.faiss")
    map_b = os.path.join(base, "id_mapping.pkl")
    if os.path.exists(idx_b) and os.path.exists(map_b):
        return idx_b, map_b

    # If nothing found, still return the most likely A to help logging
    return idx_a, map_a


def load_vector_store() -> None:
    """Load embedding model and FAISS index on startup."""
    global _embed_model, _faiss_index, _course_id_mapping

    try:
        logger.info(f"[retrieval] Loading embedding model: {settings.embed_model_name}")
        _embed_model = SentenceTransformer(settings.embed_model_name)

        base_path = settings.faiss_index_path  # could be folder or file depending on env
        index_file, mapping_file = _resolve_faiss_paths(base_path)

        if not index_file or not mapping_file:
            logger.warning("[retrieval] FAISS paths not configured. Semantic search disabled.")
            _faiss_index = None
            _course_id_mapping = None
            return

        exists_idx = os.path.exists(index_file)
        exists_map = os.path.exists(mapping_file)

        if not (exists_idx and exists_map):
            logger.warning(
                "[retrieval] FAISS index not found.\n"
                f"  base={base_path}\n"
                f"  expected_index={index_file} (exists={exists_idx})\n"
                f"  expected_mapping={mapping_file} (exists={exists_map})\n"
                "  Semantic search disabled → will use fallback search."
            )
            _faiss_index = None
            _course_id_mapping = None
            return

        logger.info(f"[retrieval] Loading FAISS index from: {index_file}")
        _faiss_index = faiss.read_index(index_file)

        with open(mapping_file, "rb") as f:
            _course_id_mapping = pickle.load(f)

        if not isinstance(_course_id_mapping, list) or not _course_id_mapping:
            logger.warning("[retrieval] id_mapping.pkl is empty/invalid. Semantic search disabled.")
            _faiss_index = None
            _course_id_mapping = None
            return

        logger.info(f"[retrieval] ✓ FAISS loaded: ntotal={_faiss_index.ntotal}, mapping={len(_course_id_mapping)}")

    except Exception as e:
        logger.exception(f"[retrieval] Failed to load vector store: {e}")
        _embed_model = None
        _faiss_index = None
        _course_id_mapping = None


# -------------------------------------------------------------------
# Exact / Fuzzy title retrieval
# -------------------------------------------------------------------
async def retrieve_by_exact_title(
    db: AsyncSession,
    title: str,
    fuzzy_threshold: Optional[int] = None,
    max_scan: int = 2000
) -> Tuple[Optional[CourseSchema], List[str]]:
    """
    Retrieve course by exact or fuzzy title match.

    Returns:
        (matched_course or None, list of suggested titles)
    """
    title = _normalize_text(title)
    if not title:
        return None, []

    threshold = fuzzy_threshold or settings.fuzzy_match_threshold

    # Exact case-insensitive match (fast via index on lower(title))
    stmt = select(Course).where(func.lower(Course.title) == title.lower())
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if course:
        logger.info(f"[retrieval] Exact title match: {course.title}")
        return CourseSchema.from_orm(course), []

    # Fuzzy: avoid loading everything blindly if huge.
    # We can narrow with ILIKE first (token-based heuristic).
    tokens = [t for t in re.split(r"\s+", title) if len(t) >= 3]
    like_stmt = select(Course).limit(max_scan)
    if tokens:
        # OR ILIKE on tokens to reduce candidates
        ors = [Course.title.ilike(f"%{tok}%") for tok in tokens[:5]]
        like_stmt = like_stmt.where(or_(*ors)).limit(max_scan)

    result = await db.execute(like_stmt)
    candidates = result.scalars().all()

    scored: List[Tuple[Course, int]] = []
    for c in candidates:
        sc = fuzz.ratio(title.lower(), (c.title or "").lower())
        scored.append((c, sc))
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored and scored[0][1] >= threshold:
        best = scored[0][0]
        logger.info(f"[retrieval] Fuzzy title match: {best.title} (score={scored[0][1]})")
        return CourseSchema.from_orm(best), []

    # Suggestions: return top 3 even if below threshold (useful UX)
    suggestions = [c.title for c, _ in scored[:3]]
    logger.info(f"[retrieval] No title match for '{title}'. Suggestions={suggestions}")
    return None, suggestions


# -------------------------------------------------------------------
# Semantic retrieval (FAISS)
# -------------------------------------------------------------------
async def retrieve_by_semantic(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[CourseSchema]:
    """
    Semantic search with FAISS. Falls back if vector store isn't available.

    filters: {"level": "...", "category": "..."}
    """
    query = _normalize_text(query)
    if not query:
        return []

    if not _embed_model or not _faiss_index or not _course_id_mapping:
        logger.warning("[retrieval] Vector store not loaded. Using fallback search.")
        return await fallback_search(db, query, top_k=top_k, filters=filters)

    # Encode query (E5 recommended prefix + normalize)
    q = _e5_query(query)
    vec = _embed_model.encode([q], normalize_embeddings=False)
    vec = np.asarray(vec, dtype=np.float32)
    vec = _l2_normalize(vec)

    # Search FAISS
    # request more for filtering, but cap
    request_k = min(max(top_k * 4, 20), len(_course_id_mapping))
    distances, indices = _faiss_index.search(vec, request_k)

    # Collect IDs safely (ignore -1)
    retrieved_ids: List[str] = []
    for idx in indices[0].tolist():
        if idx is None or idx < 0:
            continue
        if idx >= len(_course_id_mapping):
            continue
        retrieved_ids.append(str(_course_id_mapping[idx]))

    if not retrieved_ids:
        logger.info("[retrieval] FAISS returned 0 valid ids. Using fallback search.")
        return await fallback_search(db, query, top_k=top_k, filters=filters)

    # Convert to UUIDs for DB query
    uuid_ids = [u for u in (_safe_uuid(x) for x in retrieved_ids) if u is not None]
    if not uuid_ids:
        logger.warning("[retrieval] Retrieved ids could not be parsed as UUID. Using fallback.")
        return await fallback_search(db, query, top_k=top_k, filters=filters)

    stmt = select(Course).where(Course.course_id.in_(uuid_ids))

    # Apply filters (case-insensitive exact)
    if filters:
        lvl = filters.get("level")
        cat = filters.get("category")
        if lvl:
            stmt = stmt.where(func.lower(Course.level) == lvl.lower())
        if cat:
            stmt = stmt.where(func.lower(Course.category) == cat.lower())

    result = await db.execute(stmt)
    courses = result.scalars().all()

    # Preserve FAISS order
    course_dict = {str(c.course_id): c for c in courses}
    ordered = [course_dict[str(cid)] for cid in uuid_ids if str(cid) in course_dict]
    ordered = ordered[:top_k]

    logger.info(f"[retrieval] Semantic search returned {len(ordered)} courses")
    return [CourseSchema.from_orm(c) for c in ordered]


# -------------------------------------------------------------------
# Fallback retrieval (Multilingual-safe)
# -------------------------------------------------------------------
async def fallback_search(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[CourseSchema]:
    """
    Multilingual fallback:
    - If Arabic detected or mixed: use ILIKE-based search (works for Arabic).
    - Else: try FTS English + ILIKE as backup.

    Production note:
    For better quality, enable pg_trgm and use similarity() or % operator.
    """
    query = _normalize_text(query)
    if not query:
        return []

    is_ar = _contains_arabic(query)

    # Base statement
    stmt = select(Course)

    # Filters first (so we search less)
    if filters:
        lvl = filters.get("level")
        cat = filters.get("category")
        if lvl:
            stmt = stmt.where(func.lower(Course.level) == lvl.lower())
        if cat:
            stmt = stmt.where(func.lower(Course.category) == cat.lower())

    # Optimized pg_trgm Search (Production)
    q = query.lower()
    WSIM_THRESHOLD = 0.12

    # Logic:
    # 1. Prefilter with '%' (trigram similarity op) to leverage index (gin_trgm_ops)
    # 2. Gate with word_similarity >= 0.12 to cut noise
    # 3. Rank by word_similarity desc

    # Construct statement
    stmt = stmt.where(
        func.lower(Course.title).op('%')(q)
    ).where(
        func.word_similarity(func.lower(Course.title), q) >= WSIM_THRESHOLD
    )
    
    # Advanced: Add description if title match is weak?
    # For now, following user instruction strictly for title-focused retrieval
    
    # Ordering
    stmt = stmt.order_by(
        func.word_similarity(func.lower(Course.title), q).desc()
    ).limit(top_k)

    result = await db.execute(stmt)
    courses = result.scalars().all()
    
    if courses:
        logger.info(f"[retrieval] Optimized pg_trgm returned {len(courses)} courses")
        return [CourseSchema.from_orm(c) for c in courses]
        
    # If optimization returns nothing, fallback to simple ILIKE for robustness (optional but good for safety)
    # Keeping it simple as requested - if they provided specific SQL logic, they assume DB has extension enabled.
    logger.info("[retrieval] Optimized pg_trgm returned 0. Trying rough containment ILIKE.")
    
    ilike_stmt = select(Course).where(
        or_(
            Course.title.ilike(f"%{query}%"),
            Course.description.ilike(f"%{query}%")
        )
    ).limit(top_k)
    
    res = await db.execute(ilike_stmt)
    fallback_courses = res.scalars().all()
    return [CourseSchema.from_orm(c) for c in fallback_courses]


# -------------------------------------------------------------------
# Suggestions
# -------------------------------------------------------------------
async def suggest_similar_titles(db: AsyncSession, title: str, top_k: int = 3) -> List[str]:
    """Get similar course titles for suggestions (always returns best 3, even if low score)."""
    title = _normalize_text(title)
    if not title:
        return []

    stmt = select(Course.title)
    result = await db.execute(stmt)
    all_titles = [row[0] for row in result.all() if row and row[0]]

    scored = [(t, fuzz.ratio(title.lower(), t.lower())) for t in all_titles]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [t for t, _ in scored[:top_k]]
