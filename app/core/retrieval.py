# app/core/retrieval.py
from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional
import pandas as pd
import json
from pathlib import Path

LEVEL_ORDER = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
LEVELS = ["Beginner", "Intermediate", "Advanced"]

# =========================
# Paths / Lexicon loading
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # .../Career Copilot RAG
LEXICON_PATH = BASE_DIR / "data" / "user_topic_lexicon.json"

LEXICON_TOPICS: Dict[str, dict] = {}   # topic_id -> topic data
LEXICON_ALIASES: Dict[str, str] = {}   # alias -> topic_id

def _safe_lower(x: str) -> str:
    return (x or "").strip().lower()

if LEXICON_PATH.exists():
    try:
        with open(LEXICON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for t in data.get("topics", []):
            tid = t.get("id")
            if not tid:
                continue
            LEXICON_TOPICS[tid] = t

            for alias in t.get("aliases", []):
                a = _safe_lower(alias)
                if a:
                    LEXICON_ALIASES[a] = tid

            # Also map display names as aliases
            de = _safe_lower(t.get("display_en", ""))
            da = _safe_lower(t.get("display_ar", ""))
            if de:
                LEXICON_ALIASES[de] = tid
            if da:
                LEXICON_ALIASES[da] = tid

    except Exception as e:
        print(f"[retrieval.py] Error loading lexicon: {e}")


# =========================
# Deterministic synonym expansion (STRICT)
# =========================
EXPAND: Dict[str, List[str]] = {
    # Databases / SQL / MySQL
    "sql": ["sql", "mysql", "my sql", "database", "databases", "db", "قواعد البيانات", "داتا بيز", "داتابيز"],
    "mysql": ["mysql", "my sql", "m y sql"],
    "db": ["db", "database", "databases", "data base", "قواعد البيانات", "داتا بيز", "داتابيز"],
    "database": ["database", "databases", "db", "data base", "قواعد البيانات", "داتا بيز", "داتابيز"],

    # Access DB vs Edge (important)
    "ms access": ["access 2019", "microsoft access", "ms access", "access database", "access db", "اكسس", "مايكروسوفت اكسس", "access"],
    "edge": ["microsoft edge", "edge", "windows microsoft edge"],

    # Programming
    "python": ["python", "py", "بايثون", "بيثون", "بايثن", "p y t h o n"],
    "php": ["php", "p h p", "بي اتش بي", "بي إتش بي", "بيتشبي", "php 2020"],
    "js": ["javascript", "java script", "js", "j s", "جافاسكريبت", "جافا سكريبت", "hava script", "javasript", "jav script"],
    "javascript": ["javascript", "java script", "js", "hava script", "جافاسكريبت"],

    # Web / WP
    "web": ["web", "web development", "frontend", "front end", "backend", "back end", "fullstack", "full stack", "ويب", "مواقع", "تطوير ويب"],
    "wordpress": ["wordpress", "word press", "wp", "ووردبريس", "وردبريس"],

    "html": ["html", "h t m l", "html5", "اتش تي ام ال"],
    "css": ["css", "c s s", "css3", "سي اس اس"],

    # 3D / CAD / Design tools
    "3d": ["3d", "3 d", "3d max", "3ds max", "3dsmax", "3dmax", "ثري دي", "3دي", "ثري دي ماكس", "3d_max"],
    "3d max": ["3d max", "3ds max", "3dsmax", "3dmax", "ثري دي ماكس", "3d_max"],
    "autocad": ["autocad", "auto cad", "cad", "اوتوكاد", "أوتوكاد", "autocad 3d"],
    "revit": ["revit", "ريفيت", "ريفِت", "autodesk revit"],
    "illustrator": ["illustrator", "adobe illustrator", "ai illustrator", "اليستريتور", "إليستريتور", "Adobe Illustrator"],
    "photoshop": ["photoshop", "adobe photoshop", "ps", "فوتوشوب", "Adobe Photoshop"],
    "after effects": ["after effects", "aftereffect", "ae", "افتر افكتس", "أفتر إفكتس", "Adobe After Effects"],

    # Office
    "excel": ["excel", "اكسل", "إكسل", "advanced excel"],
    "powerpoint": ["powerpoint", "power point", "بوربوينت"],

    # Mobile (Android)
    "android": ["android", "android studio", "اندرويد", "أندرويد", "اندرويد ستوديو"],

    # Security
    "security": ["data security", "security", "cyber", "cybersecurity", "hacking", "keylogger", "أمن معلومات", "اختراق", "هاكينج"],
    "hacking": ["hacking", "hack", "keylogger", "اختراق", "هاكينج"],

    # Business / Mgmt / Marketing
    "management": ["management", "leadership", "manager", "leading", "leader", "influence", "إدارة", "ادارة", "الادارة", "الإدارة", "قيادة", "مدير"],
    "leadership": ["leadership", "leading", "leader", "influence", "قيادة", "مهارات القيادة", "تأثير"],
    "marketing": ["marketing", "market", "digital marketing", "branding", "seo", "تسويق", "ماركتنج", "تسويق رقمي"],
    "business": ["business", "business fundamentals", "business basics", "بيزنس", "أساسيات الأعمال", "أساسيات البيزنس"],

    # Broad umbrella (use with care)
    "graphic design": ["graphic design", "design", "تصميم", "ديزاين", "جرافيك", "photoshop", "illustrator", "after effects", "3d max", "autocad", "revit"],
}

# =========================
# Hard exclusions to prevent forever-mixing
# =========================
EXCLUDE: Dict[str, List[str]] = {
    # prevent Access DB from catching Edge course
    "ms access": ["edge", "microsoft edge", "windows microsoft edge"],

    # prevent databases from mixing with hacking
    "sql": ["keylogger", "hacking"],
    "database": ["keylogger", "hacking"],
    "mysql": ["keylogger", "hacking"],

    # prevent 3d max from pulling autocad/revit if user asked strictly 3d max
    "3d max": ["autocad", "revit"],
}


# =========================
# Normalization / intent detection
# =========================
def normalize_topic(user_text: str) -> Tuple[str, str, bool]:
    """
    Returns (normalized_topic_or_topic_id, detected_language, intent_detected)
    - If lexicon exact match exists -> returns topic_id
    - Otherwise returns a cleaned candidate topic string
    """
    text = user_text or ""

    # Language detection (simple)
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    lang = "ar" if ar > 0 else "en"

    # Basic cleanup
    t = _safe_lower(text)
    t = re.sub(r"\s+", " ", t)

    # 1) Exact lexicon match
    if t in LEXICON_ALIASES:
        return LEXICON_ALIASES[t], lang, True

    intent_detected = False

    # 2) Lightweight typo fixes (safe)
    replacements = {
        "hava script": "javascript",
        "java script": "javascript",
        "tolearn": "to learn",
        "i wont": "i want",
        "data base": "database",
        "داتا بيز": "database",
        "داتابيز": "database",
        "الادارة": "management",
        "ادارة": "management",
        "قيادة": "leadership",
        "تسويق": "marketing",
        "بيزنس": "business",
    }
    for old, new in replacements.items():
        if old in t:
            t = t.replace(old, new)
            intent_detected = True

    # 3) Extract topic candidate from learning intent phrases
    prefixes = r"(learn|learning|course|courses|start|study|studying|at3lm|3awz|3ayz|اتعلم|أتعلم|كورس|دورة|تعليم|تعلم|عاوز|عايز|ابقى|اكون|اريد|عايز اتعلم|عاوز اتعلم)"
    m = re.search(rf"{prefixes}\s+([a-z0-9\+\#\-\s\u0600-\u06FF]{{1,40}})", t)

    clean_candidate = t
    if m:
        intent_detected = True
        cand = (m.group(2) or "").strip()

        # Remove any repeated prefix from beginning of candidate (safe)
        cand = re.sub(rf"^{prefixes}\s+", "", cand).strip()

        # If too long, keep first 1-2 tokens (but allow "3d max", "ms access")
        parts = cand.split()
        if len(parts) > 2:
            two = " ".join(parts[:2])
            if two in ("3d max", "ms access"):
                cand = two
            else:
                cand = parts[0]

        clean_candidate = cand.strip()

    # 4) Check lexicon after stripping
    if clean_candidate in LEXICON_ALIASES:
        return LEXICON_ALIASES[clean_candidate], lang, True

    # 5) If user typed a known keyword, treat as intent
    known_keys = {
        "java", "python", "php", "sql", "mysql", "javascript", "js",
        "html", "css", "3d", "3d max", "excel", "programming", "برمجة",
        "database", "ms access", "graphic design", "design", "management",
        "business", "marketing", "leadership", "wordpress", "autocad", "revit",
        "illustrator", "photoshop", "after effects", "android", "security", "hacking",
    }
    if clean_candidate in known_keys:
        intent_detected = True

    return clean_candidate, lang, intent_detected


# =========================
# Course Title Matching (Exact + Fuzzy)
# =========================
from difflib import get_close_matches

def find_course_by_title(
    user_text: str,
    df: pd.DataFrame,
    *,
    cutoff: float = 0.7,
    max_results: int = 1
) -> Optional[dict]:
    """
    Attempt to find a course by exact or fuzzy title match.
    Returns the best matching course dict if found, else None.
    
    Priority:
    1. Exact title match (case-insensitive)
    2. Partial substring match (title contains query or query contains title)
    3. Fuzzy match via difflib
    """
    _ensure_cols(df)
    
    if not user_text or df.empty:
        return None
    
    # Normalize user text
    query = _safe_lower(user_text)
    
    # Remove common prefixes that indicate title search
    title_prefixes = [
        r"عاوز كورس\s*", r"عايز كورس\s*", r"كورس اسمه\s*", r"كورس\s*",
        r"course named\s*", r"course called\s*", r"give me\s*", r"find\s*",
        r"show me\s*", r"ابحث عن\s*", r"دورة\s*"
    ]
    clean_query = query
    for prefix in title_prefixes:
        clean_query = re.sub(rf"^{prefix}", "", clean_query, flags=re.IGNORECASE).strip()
    
    if not clean_query or len(clean_query) < 3:
        return None
    
    # Build title list
    titles_lower = df["title"].fillna("").astype(str).str.lower().tolist()
    titles_original = df["title"].fillna("").astype(str).tolist()
    
    # 1) Exact match
    for idx, title in enumerate(titles_lower):
        if title == clean_query:
            return _course_row_to_dict(df.iloc[idx])
    
    # 2) Substring match (user typed part of title or title contains query)
    for idx, title in enumerate(titles_lower):
        if clean_query in title or title in clean_query:
            return _course_row_to_dict(df.iloc[idx])
    
    # 3) Fuzzy match
    matches = get_close_matches(clean_query, titles_lower, n=max_results, cutoff=cutoff)
    if matches:
        best = matches[0]
        idx = titles_lower.index(best)
        return _course_row_to_dict(df.iloc[idx])
    
    return None


def _course_row_to_dict(row: pd.Series) -> dict:
    """Convert a DataFrame row to a course dict with all fields."""
    course_id = ""
    if "course_id" in row:
        course_id = str(row["course_id"])
    elif "id" in row:
        course_id = str(row["id"])
    
    return {
        "course_id": course_id,
        "title": str(row.get("title", "")),
        "category": str(row.get("category", "")),
        "level": str(row.get("level", "")),
        "instructor": str(row.get("instructor", "")),
        "duration_hours": float(row["duration_hours"]) if pd.notna(row.get("duration_hours")) and str(row.get("duration_hours")).strip() != "" else 0.0,
        "skills": str(row.get("skills", "")) if pd.notna(row.get("skills")) else "",
        "description": str(row.get("description", "")) if pd.notna(row.get("description")) else "",
    }


# =========================
# Regex helpers
# =========================
def _word_regex(term: str) -> str:
    term = re.escape(_safe_lower(term))
    if not term:
        return r"UNUSED_PATTERN"
    # Word boundary-ish
    return rf"(?<!\w){term}(?!\w)"


def _get_id_col(df: pd.DataFrame) -> Optional[str]:
    if "course_id" in df.columns:
        return "course_id"
    if "id" in df.columns:
        return "id"
    return None


def _ensure_cols(df: pd.DataFrame) -> None:
    # Ensure required columns exist to avoid KeyErrors
    for c in ["title", "category", "level", "instructor", "skills", "description", "duration_hours"]:
        if c not in df.columns:
            df[c] = ""


# =========================
# Retrieval
# =========================
def get_courses_by_topic(
    topic: str,
    df: pd.DataFrame,
    *,
    max_per_level: Optional[int] = None,  # None => no limit
    profiles: Optional[Dict] = None  # legacy arg support (unused)
) -> Dict[str, List[dict]]:
    """
    Returns {"Beginner":[...], "Intermediate":[...], "Advanced":[...]}
    - Deterministic path: lexicon topic_id -> matched_course_ids
    - Heuristic path: strict title match first; ONLY if title returns 0, fall back to skills/description
    - Applies EXCLUDE rules to prevent mixing
    """
    _ensure_cols(df)

    topic = _safe_lower(topic)
    if not topic:
        return {lvl: [] for lvl in LEVELS}

    matched = pd.DataFrame()

    # 1) Lexicon deterministic retrieval
    if topic in LEXICON_TOPICS:
        course_ids = LEXICON_TOPICS[topic].get("matched_course_ids", []) or []
        id_col = _get_id_col(df)
        if id_col and course_ids:
            matched = df[df[id_col].isin(course_ids)].copy()

    # 2) Heuristic retrieval (only if lexicon gave nothing)
    if matched.empty:
        terms = [topic]
        if topic in EXPAND:
            terms = list(dict.fromkeys([topic] + EXPAND[topic]))  # preserve order, unique

        title = df["title"].fillna("").astype(str).str.lower()
        skills = df["skills"].fillna("").astype(str).str.lower()
        desc = df["description"].fillna("").astype(str).str.lower()

        # Stage A: STRICT title word match
        mask_a = pd.Series([False] * len(df))
        for term in terms:
            pat = _word_regex(term)
            mask_a = mask_a | title.str.contains(pat, regex=True, na=False)

        matched = df[mask_a].copy()

        # Stage B: ONLY if Stage A is empty -> search skills/desc (still strict)
        if matched.empty:
            mask_b = pd.Series([False] * len(df))
            for term in terms:
                pat = _word_regex(term) if len(_safe_lower(term)) <= 6 else re.escape(_safe_lower(term))
                mask_b = mask_b | skills.str.contains(pat, regex=True, na=False) | desc.str.contains(pat, regex=True, na=False)
            matched = df[mask_b].copy()

    if matched.empty:
        return {lvl: [] for lvl in LEVELS}

    # 3) Apply exclusions (hard block)
    ex_terms = EXCLUDE.get(topic, []) or []
    if ex_terms:
        title_m = matched["title"].fillna("").astype(str).str.lower()
        skills_m = matched["skills"].fillna("").astype(str).str.lower()
        desc_m = matched["description"].fillna("").astype(str).str.lower()

        ex_mask = pd.Series([False] * len(matched), index=matched.index)
        for ex in ex_terms:
            ex_pat = _word_regex(ex) if len(_safe_lower(ex)) <= 6 else re.escape(_safe_lower(ex))
            ex_mask = ex_mask | title_m.str.contains(ex_pat, regex=True, na=False) \
                             | skills_m.str.contains(ex_pat, regex=True, na=False) \
                             | desc_m.str.contains(ex_pat, regex=True, na=False)

        matched = matched[~ex_mask].copy()

    if matched.empty:
        return {lvl: [] for lvl in LEVELS}

    # 4) Sort + de-duplicate
    matched["level_rank"] = matched["level"].map(LEVEL_ORDER).fillna(99).astype(int)
    matched = matched.sort_values(["level_rank", "title"], ascending=[True, True])

    # De-dupe by ID if possible, else by title
    id_col = _get_id_col(matched)
    if id_col:
        matched = matched.drop_duplicates(subset=[id_col])
    else:
        matched = matched.drop_duplicates(subset=["title"])

    grouped: Dict[str, List[dict]] = {lvl: [] for lvl in LEVELS}

    # Use best-effort id field in output
    out_id_col = _get_id_col(df)  # prefer df's naming

    for lvl in LEVELS:
        lvl_df = matched[matched["level"] == lvl].copy()

        if max_per_level is not None:
            lvl_df = lvl_df.head(max_per_level)

        rows: List[dict] = []
        for _, r in lvl_df.iterrows():
            # Resolve course_id field safely
            course_id_val = ""
            if out_id_col and out_id_col in r:
                course_id_val = str(r[out_id_col])
            elif "course_id" in r:
                course_id_val = str(r["course_id"])
            elif "id" in r:
                course_id_val = str(r["id"])

            rows.append({
                "course_id": course_id_val,
                "title": str(r.get("title", "")),
                "category": str(r.get("category", "")),
                "level": str(r.get("level", "")),
                "instructor": str(r.get("instructor", "")),
                "duration_hours": float(r["duration_hours"]) if pd.notna(r.get("duration_hours")) and str(r.get("duration_hours")).strip() != "" else 0.0,
                "skills": str(r.get("skills", "")) if pd.notna(r.get("skills")) else "",
                "description": str(r.get("description", "")) if pd.notna(r.get("description")) else "",
            })

        grouped[lvl] = rows

    return grouped


def flatten_grouped(grouped: Dict[str, List[dict]]) -> List[dict]:
    out: List[dict] = []
    for lvl in LEVELS:
        out.extend(grouped.get(lvl, []))
    return out
