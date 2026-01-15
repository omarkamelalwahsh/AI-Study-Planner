import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedQuery:
    intent_type: str      # "category_query" | "exact_course_query" | "topic_search" | "no_match"
    topic: Optional[str]
    category: Optional[str]
    level: Optional[str]  # "Beginner" | "Intermediate" | "Advanced" | None
    level_mode: str       # "single_level" | "all_levels"
    search_text: Optional[str]
    reasoning: str

# Intent Constants
INTENT_CATEGORY = "category_query"
INTENT_EXACT_COURSE = "exact_course_query"
INTENT_TOPIC = "topic_search"
INTENT_NO_MATCH = "no_match"

LEVEL_MAP = {
    # Arabic
    "مبتدئ": "Beginner",
    "مبتدئين": "Beginner",
    "للمبتدئين": "Beginner",
    "متوسط": "Intermediate",
    "متوسطة": "Intermediate",
    "للمتوسط": "Intermediate",
    "متقدم": "Advanced",
    "متقدمين": "Advanced",
    "للمتقدمين": "Advanced",
    # English
    "beginner": "Beginner",
    "beginners": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "expert": "Advanced"
}

# كلمات نية وحشو (ممكن تزود براحتك)
FILLER_WORDS = {
    "انا","أنا","عاوز","عايز","اريد","أريد","ابغى","أبغى","بدي",
    "اتعلم","أتعلم","تعلم","تعليمي","محتاج","نفسي","لو","سمحت",
    "عاوزه","عايزه","في","على","من","الى","إلى","عن","مع","بس","فقط","كده",
    "مازلت", "مازال", "لسه", "كنت", "يعني", "دورة", "كورس", "شرح"
}

LATIN_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9\+\#\.\- ]{0,40}")

def parse_query_basic(user_query: str) -> tuple[str, Optional[str], str]:
    """
    Helper to extract raw (topic_candidate, level, level_mode) from query.
    Does NOT determine intent. This is used by the Router/Brain to decide intent.
    """
    if not user_query:
        return "", None, "all_levels"

    q = user_query.strip()

    # 1) Extract level (Arabic/English)
    level = None
    q_lower = q.lower()
    
    # Check for level words
    # We prioritize longest match if possible, but simple iteration is usually fine for these distinct keys
    for key, val in LEVEL_MAP.items():
        # strict word boundary check might be better, but user snippet used simple 'in'
        # Let's verify if 'in' is safe. "intermediate" in "intermediate" -> ok.
        # "beginner" in "beginners" -> ok (val is Beginner).
        if key in q_lower:
            level = val
            break

    # 2) Extract topic:
    # Prefer latin-ish chunk (sql, python, c#, c++, 3d max, mysql...)
    # The RegEx tries to grab Latin characters/numbers and some symbols.
    m = LATIN_TOKEN_RE.search(q)
    if m:
        topic = m.group(0).strip()
    else:
        # fallback: remove filler words and level words, keep remaining Arabic tokens
        # Standardize "q" normalization for token removal if needed, but here we do simple split
        tokens = [t for t in re.split(r"\s+", q) if t]
        
        # Filter fillers and level keys
        cleaned_tokens = []
        for t in tokens:
            # Check against fillers
            if t in FILLER_WORDS: 
                continue
            # Check against level map keys (fuzzy)
            is_level_word = False
            for k in LEVEL_MAP:
                if k == t.lower(): # exact word match for removal
                    is_level_word = True
                    break
            if is_level_word:
                continue
            
            cleaned_tokens.append(t)
            
        topic = " ".join(cleaned_tokens).strip()

    if not topic:
        # آخر fallback: استخدم النص الأصلي (بس غالبًا مش هيحصل)
        topic = q

    level_mode = "single_level" if level else "all_levels"
    level_mode = "single_level" if level else "all_levels"
    return topic, level, level_mode
