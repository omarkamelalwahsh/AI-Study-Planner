import os
import re
import logging
import numpy as np
from typing import List, Any
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------
# 1) GRAPHITI Arabic normalization
# -----------------------------
# Unified Stopwords & Generic Terms (Arabic + English)
# Unified Stopwords & Generic Terms (Arabic + English)
STOPWORDS = {
    # Arabic common
    "في", "من", "على", "الى", "إلى", "عن", "مع", "كيف", "ازاي", "اتعلم", "تعلم",
    "اساسيات", "مبادئ", "مقدمه", "مقدمة", "تمهيدي", "كورس", "دوره", "دورة", "تدريب", "شرح", "دليل",
    "مسار", "تراك", "ابدأ", "بداية", "تطوير", "تنصح", "رايك", "كويس", "جيد", "افضل", "مناسب",
    "هل", "ما", "هذا", "هذه", "دي", "ده", "انا", "عايز", "عايزه", "عاوز", "عاوزه", "اريد", "ابغى", "محتاج", "محتاجه", "بدور",
    "مازلت", "مازال", "لسه", "كنت", "يعني",
    # Level keywords Arabic
    "مبتدئ", "مبتدا", "متوسط", "متقدم", "محترف", "خبير",
    # English common
    "fundamentals", "basic", "basics", "introduction", "intro", "overview", "essential", "essentials",
    "kick", "start", "kickstart", "course", "courses", "training", "tutorial", "guide", "masterclass", "complete",
    "career", "development", "learn", "study", "recommend", "suggestion", "good", "best", "ok", "worth",
    "is", "this", "a", "an", "the", "for", "to", "in", "on", "of", "and", "or", "with", "what", "how",
    # Level keywords English
    "beginner", "beginners", "intermediate", "advanced", "expert", "professional"
}

GENERIC_TERMS = {
    # Terms that if they appear alone, should be considered "Generic" -> No Match
    # (Same as stopwords effectively for keyword extraction, but explicit for logic)
    "opinion": {
        "is this a good course", "recommend", "تنصح", "كورس كويس", "رايك", "good course",
        "best course", "course review", "worth it", "which course"
    },
    "learning": {
        "course", "tutorial", "learn", "study", "training", "guide", "intro", "introduction",
        "كورس", "دورة", "شرح", "تعلم", "تعليم"
    }
}

def normalize_ar(text: str) -> str:
    """
    Apply GRAPHITI Arabic normalization rules:
    - Remove diacritics (tashkeel)
    - (أ، إ، آ → ا)
    - (ة → ه)
    - (ى → ي)
    - Unify numbers
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Remove diacritics
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    
    # 2. Normalize Alef
    text = re.sub(r"[أإآ]", "ا", text)
    
    # 3. Normalize Ta Marbuta
    text = re.sub(r"ة", "ه", text)
    
    # 4. Normalize Ya / Alef Maqsura
    text = re.sub(r"ى", "ي", text)
    
    # 5. Unify numbers (Hindi digits -> Arabic digits)
    hindi_digits = "٠١٢٣٤٥٦٧٨٩"
    arabic_digits = "0123456789"
    text = text.translate(str.maketrans(hindi_digits, arabic_digits))
    
    # Clean up whitespace and lowercase
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

# -----------------------------
# 2) Bilingual Query Expansion
# -----------------------------
EXPANSION_DICT = {
    "الصحه النفسيه": "mental health psychology",
    "تحليل بيانات": "data analysis",
    "ذكاء اصطناعي": "artificial intelligence ai",
    "تعلم الي": "machine learning",
    "برمجه": "programming",
    "جافا": "java",
    "بايثون": "python",
    "بايثون3": "python",
    "باثون": "python",
    "جافاسكربت": "javascript js",
    "سي شارب": "c# csharp",
    "سي بلس بلس": "c++",
    "قواعد بيانات": "database sql",
    "js": "javascript",
    "مبتدا": "beginner",
    "مبتدئ": "beginner",
    "مبتدئين": "beginner",
    "متوسط": "intermediate",
    "محترف": "advanced",
    "كورسات": "course courses",
    "دورة": "course",
    "تعلم": "learn learning",
    "اتعلم": "learn learning",
    "عايز": "want",
    "عاوز": "want",
    "شرح": "tutorial explained",
}

# Pre-normalize expansion keys
EXPANSION_DICT_NORM = {normalize_ar(k): v for k, v in EXPANSION_DICT.items()}

def expand_query(text: str) -> str:
    """
    Run expansion on normalized version of text.
    Returns normalized + expanded text.
    """
    if not text:
        return ""
    
    base = normalize_ar(text)
    expanded = base
    
    for k_norm, v in EXPANSION_DICT_NORM.items():
        if k_norm and k_norm in base:
            # Add value if not already present in some form
            if v.lower() not in expanded:
                expanded += f" {v}"
                
    return re.sub(r"\s+", " ", expanded).strip()

# -----------------------------
# 3) Intent Guards
# -----------------------------
LEARNING_KEYWORDS = [
    "تعلم", "اتعلم", "كورس", "دوره", "تدريب", "شرح", "مسار", "تراك", "خطه",
    "learn", "course", "tutorial", "study", "path", "guide", "roadmap",
    "start", "create", "building", "intro", "introduction", "how", "what", "basics",
    "fundamentals", "principles", "101", "zero", "master"
]

def is_generic_opinion_query(query: str) -> bool:
    if not query:
        return False

    q = normalize_ar(query)

    # Opinion / generic evaluation patterns (Arabic + English)
    patterns = [
        r"\bis this (a )?good course\b",
        r"\bis this good\b",
        r"\bgood course\b",
        r"\brecommend\b",
        r"\bis it worth\b",
        r"\bshould i\b",
        r"\bwhat do you think\b",
        r"\bok\?\b",
        r"\bهل (هذا|دي)\b",
        r"\bكورس (كويس|جيد)\b",
        r"\bهل.*(كويس|جيد|ينفع)\b",
        r"\bتنصح\b",
        r"\bرايك\b",
        r"\bمناسب\b"
    ]

    for p in patterns:
        match = re.search(p, q)
        if match:
            # Remove the detected pattern from the query
            # We use the match indices to cut it out
            remainder = q[:match.start()] + " " + q[match.end():]
            
            # If the remainder has NO subject, then it is a generic opinion query -> Return True
            if not has_subject(remainder):
                return True

    return False

def is_learning_query(query: str) -> bool:
    """
    Consider it a 'learning request' if:
    - User mentioned learning keywords (تعلم، كورس، الخ)
    - OR user simply wrote a field name (Mental Health).
    """
    if not query: return False

    # 0. Block generic opinion queries without subject
    if is_generic_opinion_query(query):
        return False
    
    norm_q = normalize_ar(query)
    
    # Rule 1: Theme/Topic alone = learning intent
    # If the query is just 1-3 words, we assume it's a topic (e.g. "Data Science")
    words = norm_q.split()
    if len(words) <= 3:
        return True

    # Rule 2: Explicit learning keywords
    if any(kw in norm_q for kw in LEARNING_KEYWORDS):
        return True

    # Rule 3: Digital/Numbered indicators (e.g. "01 Introduction", "Chapter 5")
    # If it starts with a digit, it's likely a course video/material title
    if re.match(r"^\d+", norm_q):
        return True

    return False

def has_subject(query: str) -> bool:
    """
    Check if query has enough content BEYOND keywords and generic terms.
    """
    if not query: return False
    
    norm_q = normalize_ar(query)
    
    # Split into subtokens
    tokens = norm_q.split()
    
    # Filter out learning keywords using exact match
    # normalize_ar lowercases, and keywords are lowercased.
    filtered = [t for t in tokens if t not in LEARNING_KEYWORDS]
    
    # Rejoin to check length or just check empty?
    # Logic: "at least 2 chars of content"
    clean = " ".join(filtered)
    return len(clean) >= 2

# -----------------------------
# 4) Embedding Model
# -----------------------------
class EmbeddingModel:
    _instance = None
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            model_name = settings.EMBED_MODEL_NAME or "intfloat/multilingual-e5-small"
            logger.info(f"Loading Embedding Model: {model_name}")
            cls._model = SentenceTransformer(model_name)
        return cls._model

    @classmethod
    def embed_queries(cls, queries: List[str]) -> np.ndarray:
        """
        Produce query embeddings using 'query: <text>' format and L2 normalization.
        """
        model = cls.get_model()
        # E5 expects "query: " prefix for asymmetric retrieval queries
        processed = [f"query: {expand_query(q)}" for q in queries]
        
        # normalize_embeddings=True applies L2 normalization
        embs = model.encode(processed, normalize_embeddings=True)
        return np.asarray(embs, dtype=np.float32)

    @classmethod
    def embed_passages(cls, passages: List[str]) -> np.ndarray:
        """
        Produce passage embeddings using 'passage: <text>' format and L2 normalization.
        """
        model = cls.get_model()
        # E5 expects "passage: " prefix for documents
        processed = [f"passage: {expand_query(p)}" for p in passages]
        
        embs = model.encode(processed, normalize_embeddings=True)
        return np.asarray(embs, dtype=np.float32)

def get_embedding(text: str, embedding_type: str = "query") -> Any:
    """
    Helper to get a single embedding vector (1D numpy array).
    embedding_type: 'query' or 'passage'
    """
    if not text:
        return None
    try:
        # returns [1, D]
        if embedding_type == "passage":
            embs = EmbeddingModel.embed_passages([text])
        else:
            embs = EmbeddingModel.embed_queries([text])
            
        if len(embs) > 0:
            return embs[0]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
    return None
