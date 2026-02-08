import re

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def is_arabic(text: str) -> bool:
    """Detects if the input text contains Arabic characters."""
    return bool(_ARABIC_RE.search(text or ""))
