import re

# Regex to detect if user wants courses/availability
# Covers: "courses", "do you have", "recommend me", "available", "list", "learning path with courses"
# Arabic and English variations
COURSE_ASK_RE = re.compile(
    r"(كورسات|دورات|كورس|دورة|منهج|اقترح لي|ترشيح|هل عندكم|متاح|فيه كورس|عايز اتعلم|course|courses|recommend|available|list|training|track)",
    re.IGNORECASE
)

def normalize_text(text: str) -> str:
    """Trim and basic cleanup."""
    if not text:
        return ""
    return text.strip()

def detect_language(text: str) -> str:
    """Simple heuristic for 'ar' or 'en'. Default 'ar' if mixed."""
    # Count arabic chars
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if english_chars > arabic_chars and english_chars > 3:
        return "en"
    return "ar"

def wants_courses(text: str) -> bool:
    """
    Deterministic check: Does the user explicitly imply they want to see/take courses?
    """
    return bool(COURSE_ASK_RE.search(text or ""))
