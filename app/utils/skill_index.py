import json
import os
import logging
import re
from typing import Dict, List, Set
from collections import defaultdict
# from sqlalchemy.orm import Session
# from app.models import Course
# from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Stopwords for exclusion
STOPWORDS = {
    "and", "the", "for", "in", "to", "of", "a", "an", "with", "on", "by", 
    "introduction", "basics", "advanced", "course", "tutorial", "learn", 
    "master", "complete", "guide", "essential", "essentials", "part", "level"
}

def normalize_skill(text: str) -> str:
    """Normalize skill string for indexing."""
    text = text.lower().strip()
    return text

# [MODIFIED] Builder logic disabled to fix Sync/Async DB import issues.
# User provided data/skill_to_courses_index.json, so we rely on it.
def build_skill_index() -> Dict[str, List[str]]:
    """
    Builds the skill index from the database.
    (Disabled: Requires Async Session logic update if needed in future)
    """
    logger.warning("Dynamic index building is disabled. Please ensure data/skill_to_courses_index.json exists.")
    return {}

def get_index_path() -> str:
    """Get absolute path to index file."""
    # Assuming running from root
    return os.path.join(os.getcwd(), "data", "skill_to_courses_index.json")

def save_index_to_disk(path: str = None):
    # Disabled
    pass 


# Global In-Memory Index
_MEMORY_INDEX = {}

def load_index_into_memory(path: str = None):
    global _MEMORY_INDEX
    if path is None:
        path = get_index_path()
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_index = json.load(f)
        
        # Normalize keys for insensitive lookup
        _MEMORY_INDEX = {}
        for k, v in raw_index.items():
            _MEMORY_INDEX[normalize_skill(k)] = v
            
        logger.info(f"Loaded memory index with {len(_MEMORY_INDEX)} skills from {path}.")
    except FileNotFoundError:
        logger.warning(f"Index file not found at {path}. Building fresh...")
        # Fallback: Create directory if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Note: Building fresh will use our logic which lowercases by default
        _MEMORY_INDEX = build_skill_index()
        # Save the normalized version? Or the raw? 
        # For simplicity, we save what we built.
        save_index_to_disk(path)


def find_skill_matches(query: str) -> List[Dict]:
    """
    Search the index for keys matching the query.
    Returns list of dicts: {'key': str, 'score': float, 'course_ids': list}
    """
    q_norm = normalize_skill(query)
    matches = []
    
    # 1. Exact Match
    if q_norm in _MEMORY_INDEX:
        matches.append({
            "key": q_norm,
            "score": 1.0,
            "course_ids": _MEMORY_INDEX[q_norm]
        })
        return matches # Return immediately if exact
        
    # 2. Fuzzy / Substring Search
    for key, c_ids in _MEMORY_INDEX.items():
        # Skip very short keys to reduce noise
        if len(key) < 3: continue
        
        score = 0.0
        
        # Containment (Strong)
        if q_norm == key:
            score = 1.0
        elif q_norm in key: 
            # query "Unity" inside "Unity Basics" -> Good
            # Penalize slightly based on length difference to prefer tighter matches
            # e.g. "Unity" in "Unity" (1.0) vs "Unity" in "Advanced Unity Networking" (0.8)
            ratio = len(q_norm) / len(key)
            score = 0.8 + (0.1 * ratio)
        elif key in q_norm:
            # key "Unity" inside query "I want Unity" -> Good
            ratio = len(key) / len(q_norm)
            score = 0.8 + (0.1 * ratio)
            
        if score > 0:
            matches.append({
                "key": key,
                "score": round(score, 2),
                "course_ids": c_ids
            })
            
    # Sort by score desc
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:5] # Top 5


def lookup_skill_courses(skill: str) -> List[str]:
    """
    Legacy wrapper for simple usage.
    """
    matches = find_skill_matches(skill)
    if matches:
        return matches[0]["course_ids"]
    return []
