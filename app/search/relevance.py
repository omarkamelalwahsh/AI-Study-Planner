import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.search.embedding import normalize_ar, STOPWORDS, GENERIC_TERMS

logger = logging.getLogger(__name__)

# Constants for strict filtering
MIN_SCORE = 0.78
BAND_THRESHOLD = 0.04
MAX_DISPLAY_RESULTS = 5
LEVEL_ORDER = ["Beginner", "Intermediate", "Advanced"]

def extract_keywords(text: str) -> set:
    """
    Extract meaningful keywords from text by:
    1. Arabic normalization
    2. Tokenization
    3. Removing stopwords/generic terms
    4. Removing single-char tokens
    """
    if not text:
        return set()
    
    norm = normalize_ar(text)
    # Extract words (alpha-numeric)
    words = re.findall(r'\w+', norm.lower())
    
    unique_words = set()
    for w in words:
        if len(w) > 1 and w not in STOPWORDS:
            unique_words.add(w)
    return unique_words

def is_generic_query(query: str) -> bool:
    """
    Check for generic queries that should be blocked if no subject exists.
    e.g. "Is this a good course?", "Recommend", "Help"
    
    Logic: Extract keywords (removing stopwords AND generic terms). 
    If 0 left, it's generic.
    """
    norm_q = normalize_ar(query)
    
    # We use extract_keywords which filters STOPWORDS.
    # Our STOPWORDS already includes all generic terms from requirements.
    keywords = extract_keywords(norm_q)
    return len(keywords) == 0

def check_keyword_overlap(query_keywords: set, item_text: str) -> bool:
    """
    Apply strict overlap rules with smart tech matching.
    Includes technical synonym normalization (e.g., 'بايثون' matches 'python').
    """
    if not query_keywords:
        return False
        
    item_keywords = extract_keywords(item_text)
    
    # Technical synonym mapping for overlap check
    # Many users type in Arabic but courses are in English
    TECH_MAP = {
        "بايثون": "python",
        "جافا": "java",
        "جافاسكريبت": "javascript",
        "جافاسكربت": "javascript",
        "قواعد": "sql", # قواعد بيانات
        "داتا": "data",
        "ماشين": "machine",
        "ذكاء": "ai"
    }

    # Normalize query keywords for better matching
    norm_q_keywords = set()
    for q in query_keywords:
        norm_q_keywords.add(TECH_MAP.get(q, q))
    
    # Normalize item keywords too
    norm_item_keywords = set()
    for k in item_keywords:
        norm_item_keywords.add(TECH_MAP.get(k, k))

    num_matches = 0
    for q in norm_q_keywords:
        # 1. Exact Match
        if q in norm_item_keywords:
            num_matches += 1
            continue
            
        # 2. Smart Substring Match (e.g. 'sql' matches 'mysql')
        if q == "java" and not any(k == "java" for k in norm_item_keywords):
            continue
            
        if any(q in k for k in norm_item_keywords):
            num_matches += 1
    
    num_q = len(norm_q_keywords)
    if num_q == 1:
        return num_matches >= 1
    elif num_q == 2:
        # If we have 2 distinct concepts, we want both.
        # Note: If user typed 'بايثون python', they might be the same concept.
        # But norm_q_keywords being a set handles that!
        return num_matches >= 2
    else:
        return (num_matches / num_q) >= 0.6

def apply_strict_filters(query: str, candidates: list[dict]) -> list[dict]:
    """
    ULTRA-STRICT SEMANTIC SEARCH FILTERS (Single Source of Truth)
    
    Requirements:
    1. Top 30 retrieval (enforced by caller)
    2. Sort descending by score (CRITICAL - must be first)
    3. Band filter: score >= max(0.78, top_score - 0.04)
    4. Keyword overlap check
    5. Max 5 results
    6. No fake results if 0 remain
    """
    if not candidates:
        return []
    
    # Enforce Top 30 limit (defensive)
    candidates = candidates[:30]
    
    # CRITICAL: Sort by score descending FIRST
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    
    # Extract query keywords (removing stopwords)
    q_keywords = extract_keywords(query)
    if not q_keywords:
        # Query is completely generic/stopwords -> No Match
        logger.info(f"Query '{query}' resolved to 0 keywords -> No Semantic Match.")
        return []
    
    top_score = candidates[0].get("score", 0.0)
    # Band Threshold logic
    threshold = max(top_score - BAND_THRESHOLD, MIN_SCORE)
    
    filtered = []
    for c in candidates:
        score = c.get("score", 0.0)
        
        # 1. Band Filter
        if score < threshold:
            continue
            
        # 2. Keyword Overlap Filter
        content = f"{c.get('title', '')} {c.get('description', '')} {c.get('skills', '')}"
        if check_keyword_overlap(q_keywords, content):
            filtered.append(c)
        else:
            logger.info(f"Filtered by Overlap: {c.get('title')}")
            
    # Max 5 results
    return filtered[:MAX_DISPLAY_RESULTS]

def parse_explicit_level(q: str) -> Optional[str]:
    """
    Detect explicit level mentioned in query.
    Returns: 'Beginner', 'Intermediate', 'Advanced', or None
    """
    q_norm = normalize_ar(q).lower()
    
    if re.search(r"\b(مبتدئ|مبتدا|beginner|novice)\b", q_norm):
        return "Beginner"
    if re.search(r"\b(متوسط|intermediate)\b", q_norm):
        return "Intermediate"
    if re.search(r"\b(متقدم|محترف|advanced|expert|professional)\b", q_norm):
        return "Advanced"
    return None

def normalize_level(level: str) -> str:
    """Normalize various DB level strings to standard 3 tiers."""
    if not level: return "Intermediate"
    l = level.lower().strip()
    if any(t in l for t in ["beginner", "مبتدئ"]): return "Beginner"
    if any(t in l for t in ["advanced", "متقدم", "محترف", "expert"]): return "Advanced"
    if any(t in l for t in ["intermediate", "متوسط"]): return "Intermediate"
    return "Intermediate"

def apply_level_filter(results: list[dict], target_level: Optional[str]) -> Tuple[list[dict], str]:
    """
    Apply level filter with "Level Up" logic:
    - If target_level is None, return all results (level_mode='all_levels')
    - If target_level is set, include that level AND all subsequent levels in LEVEL_ORDER.
    - If the resulting range is empty, return ALL results (level_mode='fallback_all_levels')
    """
    if not target_level:
        return results, "all_levels"
        
    # Find index of target_level in LEVEL_ORDER
    try:
        start_idx = LEVEL_ORDER.index(target_level)
        allowed_levels = LEVEL_ORDER[start_idx:]
    except ValueError:
        # Should not happen if target_level comes from parse_explicit_level
        return results, "all_levels"
        
    filtered = [r for r in results if normalize_level(r.get("level")) in allowed_levels]
    
    if not filtered:
        logger.warning(f"Level filter for '{target_level}' and above returned 0. Triggering fallback.")
        return results, "fallback_all_levels"
        
    return filtered, "level_filtered"

def group_by_level(results: list[dict]):
    """Group results by LEVEL_ORDER and sort each group by score."""
    groups = {lvl: [] for lvl in LEVEL_ORDER}
    for r in results:
        lvl = normalize_level(r.get("level"))
        if lvl in groups:
            r["normalized_level"] = lvl
            groups[lvl].append(r)
        else:
            groups["Intermediate"].append(r)

    # sort inside each level by score (descending)
    for lvl in LEVEL_ORDER:
        groups[lvl].sort(key=lambda x: float(x.get("score", 0)) if isinstance(x.get("score"), (int, float)) else 0.0, reverse=True)

    return groups
