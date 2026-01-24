"""
retrieval.py
Production-grade retrieval engine for Career Copilot courses:
- Semantic retrieval via FAISS (optional)
- Robust multilingual fallback with pg_trgm + ILIKE
- Query canonicalization + pagination (offset/page_size)
"""
from __future__ import annotations

import os
import re
import uuid
import pickle
import logging
import json
from typing import List, Optional, Tuple, Dict, Any

import numpy as np
import faiss
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer

from app.models import Course, CourseSchema
from app.config import settings

logger = logging.getLogger(__name__)

_embed_model: Optional[SentenceTransformer] = None
_faiss_index: Optional[faiss.Index] = None
_course_id_mapping: Optional[List[str]] = None

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

_AR_NOISE = {
    "عايز","عاوز","اريد","أريد","حابب","نفسي","اتعلم","أتعلم","تعلم",
    "ابدأ","أبدأ","كورس","كورسات","دورة","دورات","تفاصيل","عن","في","هل","ممكن","ايه","إيه","اي","لو","من"
}

def _normalize_text(s: str) -> str:
    return (s or "").strip()

def _contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))

def _tokenize(text: str) -> List[str]:
    text = (text or "").strip()
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return [t for t in text.split() if t]

def _canonical_variants(query: str) -> List[str]:
    q0 = _normalize_text(query)
    if not q0:
        return []
    toks = _tokenize(q0)
    cleaned = [t for t in toks if t.lower() not in _AR_NOISE and len(t) >= 2]
    cleaned_q = " ".join(cleaned).strip()

    # best single token (prefer latin)
    latin = [t for t in cleaned if re.search(r"[A-Za-z]", t)]
    best = max(latin, key=len) if latin else (max(cleaned, key=len) if cleaned else "")

    variants = []
    for v in [q0, cleaned_q, best]:
        v = _normalize_text(v)
        if v and v not in variants:
            variants.append(v)
    return variants[:4]

def _e5_query(text: str) -> str:
    return f"query: {text}"

def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms

def _resolve_faiss_paths(base: str) -> Tuple[Optional[str], Optional[str]]:
    if not base:
        return None, None
    base = os.path.normpath(base)

    if os.path.isfile(base) and base.lower().endswith(".faiss"):
        idx_file = base
        mapping_file = os.path.join(os.path.dirname(base), "id_mapping.pkl")
        return idx_file, mapping_file

    idx_a = os.path.join(base, "index.faiss", "courses.faiss")
    map_a = os.path.join(base, "index.faiss", "id_mapping.pkl")
    if os.path.exists(idx_a) and os.path.exists(map_a):
        return idx_a, map_a

    idx_b = os.path.join(base, "courses.faiss")
    map_b = os.path.join(base, "id_mapping.pkl")
    if os.path.exists(idx_b) and os.path.exists(map_b):
        return idx_b, map_b

    return idx_a, map_a

def load_vector_store() -> None:
    global _embed_model, _faiss_index, _course_id_mapping
    try:
        _embed_model = SentenceTransformer(settings.embed_model_name)
        index_file, mapping_file = _resolve_faiss_paths(settings.faiss_index_path)

        if not index_file or not mapping_file or not os.path.exists(index_file) or not os.path.exists(mapping_file):
            logger.warning("[retrieval] FAISS not available. Semantic disabled.")
            _faiss_index = None
            _course_id_mapping = None
            return

        _faiss_index = faiss.read_index(index_file)
        with open(mapping_file, "rb") as f:
            _course_id_mapping = pickle.load(f)

        if not isinstance(_course_id_mapping, list) or not _course_id_mapping:
            logger.warning("[retrieval] id_mapping invalid. Semantic disabled.")
            _faiss_index = None
            _course_id_mapping = None
            return

        logger.info("[retrieval] FAISS loaded ntotal=%s mapping=%s", _faiss_index.ntotal, len(_course_id_mapping))
    except Exception as e:
        logger.exception("[retrieval] Failed to load vector store: %s", e)
        _embed_model = None
        _faiss_index = None
        _course_id_mapping = None


async def retrieve_courses(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    offset: int = 0,
    filters: Optional[Dict[str, str]] = None
) -> List[CourseSchema]:
    """
    Unified retrieval with pagination:
    - returns results[offset: offset+top_k]
    """
    query = _normalize_text(query)
    if not query:
        return []

    # semantic first if available
    items = await retrieve_by_semantic(db, query, top_k=top_k + offset, filters=filters)
    if not items:
        items = await fallback_search(db, query, top_k=top_k + offset, filters=filters)

    if items is None:
        items = []
        
    return items[offset: offset + top_k]


async def retrieve_by_semantic(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[CourseSchema]:
    query = _normalize_text(query)
    if not query:
        return []

    if not _embed_model or not _faiss_index or not _course_id_mapping:
        return []

    q = _e5_query(query)
    vec = _embed_model.encode([q], normalize_embeddings=False)
    vec = np.asarray(vec, dtype=np.float32)
    vec = _l2_normalize(vec)

    request_k = min(max(top_k * 4, 20), len(_course_id_mapping))
    distances, indices = _faiss_index.search(vec, request_k)

    ids: List[str] = []
    for idx in indices[0].tolist():
        if idx is None or idx < 0 or idx >= len(_course_id_mapping):
            continue
        ids.append(str(_course_id_mapping[idx]))

    if not ids:
        return []

    uuid_ids = []
    for s in ids:
        try:
            uuid_ids.append(uuid.UUID(str(s)))
        except Exception:
            pass

    if not uuid_ids:
        return []

    stmt = select(Course).where(Course.course_id.in_(uuid_ids))

    if filters:
        lvl = filters.get("level")
        cat = filters.get("category")
        if lvl:
            stmt = stmt.where(func.lower(Course.level) == lvl.lower())
        if cat:
            stmt = stmt.where(func.lower(Course.category) == cat.lower())

    res = await db.execute(stmt)
    courses = res.scalars().all()

    d = {str(c.course_id): c for c in courses}
    ordered = [d[str(cid)] for cid in uuid_ids if str(cid) in d][:top_k]
    return [CourseSchema.from_orm(c) for c in ordered]


async def fallback_search(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[CourseSchema]:
    """
    pg_trgm + ILIKE fallback on title/description/skills, using canonical query variants.
    """
    query = _normalize_text(query)
    if not query:
        return []

    variants = _canonical_variants(query)
    WSIM_THRESHOLD = 0.12

    base = select(Course)
    if filters:
        lvl = filters.get("level")
        cat = filters.get("category")
        if lvl:
            base = base.where(func.lower(Course.level) == lvl.lower())
        if cat:
            base = base.where(func.lower(Course.category) == cat.lower())

    # Try pg_trgm path (title/description/skills)
    try:
        title_l = func.lower(Course.title)
        desc_l = func.lower(Course.description)
        skills_l = func.lower(Course.skills)

        prefilters = []
        gates = []
        ranks = []

        for v in variants:
            qv = v.lower()

            # % operator prefilter
            prefilters += [
                title_l.op('%')(qv),
                desc_l.op('%')(qv),
                skills_l.op('%')(qv),
            ]

            t_sim = func.word_similarity(title_l, qv)
            d_sim = func.word_similarity(desc_l, qv)
            s_sim = func.word_similarity(skills_l, qv)
            gates += [
                t_sim >= WSIM_THRESHOLD,
                d_sim >= WSIM_THRESHOLD,
                s_sim >= WSIM_THRESHOLD
            ]
            ranks.append(func.greatest(t_sim, d_sim, s_sim))

        stmt = base.where(or_(*prefilters)).where(or_(*gates))
        rank_expr = func.greatest(*ranks) if len(ranks) > 1 else ranks[0]
        stmt = stmt.order_by(rank_expr.desc()).limit(top_k)

        res = await db.execute(stmt)
        courses = res.scalars().all()
        if courses:
            return [CourseSchema.from_orm(c) for c in courses]
    except Exception as e:
        logger.warning("[retrieval] pg_trgm failed: %s. Using ILIKE.", e)

    # Robust ILIKE fallback
    ilikes = []
    for v in variants:
        ilikes += [
            Course.title.ilike(f"%{v}%"),
            Course.description.ilike(f"%{v}%"),
            Course.skills.ilike(f"%{v}%"),
        ]
    stmt = base.where(or_(*ilikes)).limit(top_k)
    res = await db.execute(stmt)
    courses = res.scalars().all()
    return [CourseSchema.from_orm(c) for c in courses]

# ============================================================
# 4) RETRIEVAL CONTROLLER PROMPT (Layer 4)
# ============================================================
RETRIEVAL_CONTROLLER_PROMPT = """You are the Retrieval Controller.

Input:
- skills_or_areas with queries

Task:
- Create a retrieval plan to search the internal catalog across ALL categories.
- For each skill/area, choose the best queries (max 2 queries per skill) to run first for high precision.
- Provide fallback queries (up to 2) for recall if precision fails.
- Provide thresholds:
  - min_score_short_query = 70
  - min_score_normal = 78

Return JSON only:

{
  "search_scope": "ALL_CATEGORIES",
  "plan": [
    {
      "canonical_en": "string",
      "primary_queries": ["query1", "query2"],
      "fallback_queries": ["query3", "query4"],
      "min_score": 78,
      "limit_per_query": 50
    }
  ],
  "dedupe_by": "course_id"
}
"""

from groq import Groq

async def generate_search_plan(skills_data: Dict) -> Dict:
    """Layer 4: Generate deterministic search plan."""
    if not skills_data or "skills_or_areas" not in skills_data:
        return {"plan": []}
        
    client = Groq(api_key=settings.groq_api_key)
    
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": RETRIEVAL_CONTROLLER_PROMPT},
                {"role": "user", "content": json.dumps(skills_data, ensure_ascii=False)} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"[RetrievalController] Failed: {e}")
        # Valid fallback: just search the skills directly
        plan = []
        for s in skills_data.get("skills_or_areas", []):
            plan.append({
                "canonical_en": s.get("canonical_en"),
                "primary_queries": s.get("queries", [])[:4],
                "fallback_queries": [],
                "min_score": 70,
                "limit_per_query": 10
            })
        return {"plan": plan, "dedupe_by": "course_id"}

async def execute_and_group_search(
    db: AsyncSession,
    search_plan: Dict
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """
    Layers 5 & 6: Execute search plan, dedupe, and group courses.
    Returns (deduped_courses_dicts, skill_to_courses_map)
    """
    deduped_map = {} # course_id -> course_dict
    skill_map = {}   # skill_en -> list of course_dicts
    
    plan_items = search_plan.get("plan", [])
    
    for item in plan_items:
        skill_en = item.get("canonical_en")
        queries = item.get("primary_queries", [])
        limit = item.get("limit_per_query", 10)
        
        # Execute search for this skill
        found_courses = []
        for q in queries:
            # We assume retrieve_courses handles semantic + keyword internally
            # For strictness, higher precision logic should be here, but using existing retrieval for now.
            courses = await retrieve_courses(db, q, top_k=limit)
            found_courses.extend(courses)
            
        # Fallback if needed? (Skipped for speed unless empty)
        if not found_courses and item.get("fallback_queries"):
             for q in item.get("fallback_queries", []):
                courses = await retrieve_courses(db, q, top_k=limit)
                found_courses.extend(courses)

        skill_map[skill_en] = []
        
        for c in found_courses:
            cid = str(c.course_id)
            c_dict = c.dict() if hasattr(c, "dict") else c.__dict__
            
            # Enrich with supported skills
            if cid not in deduped_map:
                c_dict["supported_skills"] = [skill_en]
                deduped_map[cid] = c_dict
            else:
                if skill_en not in deduped_map[cid]["supported_skills"]:
                    deduped_map[cid]["supported_skills"].append(skill_en)
            
            # Add to skill map (referencing the SAME dict object in deduped_map to keep synced)
            skill_map[skill_en].append(deduped_map[cid])

    # Convert values to list
    all_courses = list(deduped_map.values())
    
    return all_courses, skill_map

