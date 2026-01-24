import json
import logging
import re
import time
from typing import List

from groq import Groq
from app.config import settings
from app.models import RouterOutput

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = [
    "Banking Skills", "Business Fundamentals", "Career Development",
    "Creativity and Innovation", "Customer Service", "Data Security",
    "Digital Media", "Disaster Management and Preparedness",
    "Entrepreneurship", "Ethics and Social Responsibility", "Game Design",
    "General", "Graphic Design", "Health & Wellness", "Human Resources",
    "Leadership & Management", "Marketing Skills", "Mobile Development",
    "Networking", "Personal Development", "Programming", "Project Management",
    "Public Speaking", "Sales", "Soft Skills", "Sustainability",
    "Technology Applications", "Web Development"
]

# -----------------------
# Local fast detectors
# -----------------------
# FOLLOW_UP: "هل في غيرهم؟" + variants, not exact match
_FOLLOW_UP_RE = re.compile(
    r"(?:^|\s)(هل\s*في\s*(?:غيرهم|غيره|كمان)|في\s*(?:غيرهم|غيره|كمان)|غيرهم|غيره|كمان|any\s+more|show\s+more|more)(?:\s|$)",
    re.IGNORECASE
)

# AVAILABILITY: "هل ليها كورسات؟" + variants
_AVAIL_RE = re.compile(
    r"(?:^|\s)(هل\s*(?:عندكم|عندكو)\s*كورسات|هل\s*في\s*كورسات|في\s*كورسات|في\s*كورس|هل\s*ليها\s*كورسات|هل\s*له\s*كورسات|do\s+you\s+have\s+courses|any\s+courses)(?:\s|$)",
    re.IGNORECASE
)

# Arabic stopwords (light)
_AR_STOP = {
    "عايز","عاوز","اتعلم","أتعلم","محتاج","ممكن","هل","في","عن","على","ايه","إيه","ازاي","كيف",
    "تفاصيل","كورس","كورسات","بخصوص","لي","لـ","للـ","ده","دي","بس","طيب","يعني"
}

def _detect_lang(q: str) -> str:
    has_ar = bool(re.search(r"[\u0600-\u06FF]", q or ""))
    has_en = bool(re.search(r"[A-Za-z]", q or ""))
    if has_ar and has_en:
        return "mixed"
    if has_ar:
        return "ar"
    return "en"

def _extract_keywords_fallback(q: str) -> List[str]:
    q = (q or "").strip()
    # english-ish tokens
    en_tokens = re.findall(r"[A-Za-z0-9\+\#\.]{2,}", q)
    # arabic tokens
    ar_tokens = re.findall(r"[\u0600-\u06FF]{2,}", q)
    out: List[str] = []
    for t in (en_tokens + ar_tokens):
        tl = t.lower()
        if tl in _AR_STOP:
            continue
        if t not in out:
            out.append(t)
    return out[:8]

def _default_category_from_anchors(user_question: str) -> str:
    ql = (user_question or "").lower()
    if any(x in ql for x in ["data science", "scientist", "machine learning", "ml", "ai", "deep learning", "علم البيانات", "ذكاء اصطناعي"]):
        return "Programming" # Map to closest category (or Career Development if softer)
    if any(x in ql for x in ["python", "بايثون", "program", "coding", "java", "c++", "c#", "javascript", "typescript", "برمجة"]):
        return "Programming"
    if any(x in ql for x in ["web", "html", "css", "react", "frontend", "backend", "ويب", "موقع"]):
        return "Web Development"
    if any(x in ql for x in ["android", "ios", "kotlin", "swift", "flutter", "موبايل"]):
        return "Mobile Development"
    if any(x in ql for x in ["cyber", "security", "privacy", "سيبراني", "امن معلومات"]):
        return "Data Security"
    if any(x in ql for x in ["network", "tcp", "ccna", "شبكات"]):
        return "Networking"
    if any(x in ql for x in ["scrum", "agile", "pmp", "إدارة مشاريع"]):
        return "Project Management"
    if any(x in ql for x in ["resume", "cv", "interview", "portfolio", "سيرة ذاتية", "انترفيو"]):
        return "Career Development"
    if any(x in ql for x in ["excel", "powerpoint", "word", "ويندوز", "أوفيس"]):
        return "Technology Applications"
    if any(x in ql for x in ["sales", "مبيعات", "تسويق", "marketing"]):
        return "Sales"
    if any(x in ql for x in ["communication", "تواصل", "soft skills", "مهارات شخصية", "negotiation"]):
        return "Soft Skills"
    if any(x in ql for x in ["business", "entrepreneur", "startup", "management", "bussines", "businessman", "ريداة أعمال", "بيزنس", "إدارة"]):
        return "Entrepreneurship"
    return "General"

# -----------------------
# Router prompt
# -----------------------
# -----------------------
# 1) Router Prompt (app/router.py)
# -----------------------
_ROUTER_SYSTEM_PROMPT = """You are the Router.

Decide:
- intent: one of [career_guidance, course_lookup, skill_lookup, category_browse, chit_chat, admin]
- user_goal: short statement
- target_role (optional)
- language: [ar, en, mixed]
- needs_clarification: true/false (ONLY if absolutely necessary)

Rules:
- If the user message has typos but meaning is clear, silently correct.
- If the user asks "how to become X" => career_guidance intent.
- If user asks "course named X" or "عاوز كورس اسمه" => course_lookup.
- "GREETING" maps to chit_chat.
- Do NOT generate courses or skills lists here. Only routing.

Return JSON only:

{
  "intent": "...",
  "user_goal": "...",
  "target_role": "...",
  "language": "...",
  "needs_clarification": false,
  "clarification_question": "",
  "target_categories": [],
  "in_scope": true,
  "keywords": []
}

Detailed Intent Map:
- career_guidance: "How to become...", "Roadmap for...", "Skills needed for X", "azay ab2a X"
- course_lookup: "Python course", "Course about X", "Do you have X course?"
- skill_lookup: "Learn python", "Explain SQL", "What is rag?"
- category_browse: "Programming courses", "Marketing courses"
- chit_chat: "Hello", "Thanks", "Support"
"""

class GroqUnavailableError(Exception):
    pass

def classify_intent(user_question: str) -> RouterOutput:
    q_strip = (user_question or "").strip()
    lang = _detect_lang(q_strip)

    # 1. Fast Path for Follow-up
    if len(q_strip) <= 40 and _FOLLOW_UP_RE.search(q_strip):
         return RouterOutput(
            in_scope=True,
            intent="FOLLOW_UP",
            user_language=lang,
             keywords=_extract_keywords_fallback(q_strip) or ["more"]
        )
    
    # 2. Fast Path for Availability
    if len(q_strip) <= 80 and _AVAIL_RE.search(q_strip):
         # Typically course lookup
         return RouterOutput(
            in_scope=True,
            intent="AVAILABILITY_CHECK", # Maps to SEARCH internally usually
            target_categories=[_default_category_from_anchors(q_strip)],
            user_language=lang,
            keywords=_extract_keywords_fallback(q_strip)
        )

    # 3. LLM Routing
    client = Groq(api_key=settings.groq_api_key)
    
    router_input = json.dumps({
        "USER_QUESTION": user_question,
        "ALLOWED_CATEGORIES": ALLOWED_CATEGORIES
    }, ensure_ascii=False)

    max_retries = settings.groq_max_retries
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": _ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": router_input}
                ],
                temperature=0.0,
                max_tokens=350,
                timeout=settings.groq_timeout_seconds,
                response_format={"type": "json_object"}
            )
            
            content = (response.choices[0].message.content or "").strip()
            data = json.loads(content)
            
            # Map LLM intent string to Enum
            raw_intent = data.get("intent", "").lower()
            mapped_intent = "SEARCH" # Default
            
            if raw_intent == "career_guidance": mapped_intent = "CAREER_GUIDANCE"
            elif raw_intent == "course_lookup": mapped_intent = "COURSE_DETAILS" # Or SKILL_SEARCH depending on specificity
            elif raw_intent == "skill_lookup": mapped_intent = "SKILL_SEARCH"
            elif raw_intent == "category_browse": mapped_intent = "CATEGORY_BROWSE"
            elif raw_intent == "chit_chat": mapped_intent = "GREETING"
            elif raw_intent == "admin": mapped_intent = "SUPPORT_POLICY"
            
            # Adjust mapping if user asks for generic course lookup -> SKILL_SEARCH
            # The user spec differentiates course_lookup vs skill_lookup.
            # We map consistent with app/models.py
            
            out = RouterOutput(
                in_scope=data.get("in_scope", True),
                intent=mapped_intent.upper() if mapped_intent.upper() in ["CAREER_GUIDANCE", "GREETING", "FOLLOW_UP", "AVAILABILITY_CHECK", "COURSE_DETAILS", "SKILL_SEARCH", "CATEGORY_BROWSE"] else "SKILL_SEARCH",
                target_categories=data.get("target_categories", []),
                user_language=data.get("language", lang),
                user_goal=data.get("user_goal"),
                target_role=data.get("target_role"),
                keywords=data.get("keywords", []) or _extract_keywords_fallback(q_strip)
            )
            
            logger.info("Router: intent=%s role=%s goal=%s", out.intent, out.target_role, out.user_goal)
            return out
            
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            logger.error("Router failed: %s", e)
            
            # Fallback
            return RouterOutput(
                in_scope=True,
                intent="SKILL_SEARCH",
                user_language=lang,
                keywords=_extract_keywords_fallback(q_strip)
            )
    
    return RouterOutput(in_scope=True, intent="SKILL_SEARCH", user_language="en")
