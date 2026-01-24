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
_ROUTER_SYSTEM_PROMPT = """You are the ROUTER for Career Copilot. Return JSON ONLY. Do not answer the user.

You receive:
- USER_QUESTION
- ALLOWED_CATEGORIES (exact list)

Return JSON:
{
  "user_language": "en|ar|mixed",
  "in_scope": true,
  "intent": "GREETING|COURSE_DETAILS|SKILL_SEARCH|CATEGORY_BROWSE|AVAILABILITY_CHECK|FOLLOW_UP|CAREER_GUIDANCE|PLAN_REQUEST|SUPPORT_POLICY|UNSAFE|OUT_OF_SCOPE",
  "target_categories": [],
  "keywords": [],
  "course_title_candidate": null
}

Rules:

1) user_language: ar/en/mixed.

2) in_scope:
- true if maps to allowed categories OR contains any STRONG ANCHOR below.
- false only if clearly unrelated.

STRONG ANCHORS:
- Data Science / AI: data science, data scientist, machine learning, ml, deep learning, ai, علم بيانات, ذكاء اصطناعي
- Programming: python, java, c++, c#, javascript, typescript, coding, programming, بايثون, برمجة
- Web Development: html, css, react, node, frontend, backend, web, ويب, موقع
- Mobile Development: android, ios, kotlin, swift, flutter, موبايل
- Data Security: cybersecurity, security, privacy, سيبراني, امن معلومات
- Networking: network, tcp, ccna, شبكات
- Project Management: scrum, agile, pmp, إدارة مشاريع
- Career Development: resume, cv, interview, portfolio, سيرة ذاتية
- Technology Applications: excel, powerpoint, word, ويندوز, أوفيس
- Business / Entrepreneurship: business, entrepreneur, startup, management, businessman, بيزنس, ريادة أعمال, إدارة

If ANY anchor appears => in_scope=true.

3) intent selection (EXACTLY ONE):
- FOLLOW_UP: asks for more items ("هل في غيرهم", "any more", "show more").
- AVAILABILITY_CHECK: asks if courses exist ("هل ليها كورسات", "do you have courses").
- PLAN_REQUEST: asks for roadmap/schedule/timeframe ("خطة", "جدول", "weeks", "30 days").
- CAREER_GUIDANCE (CRITICAL): required skills / first skill / become good at X:
  Arabic: "المهارات المطلوبة", "ازاي أبقى شاطر", "محتاج أتعلم ايه", "ايه المهارات", "اول مهارة"
  English: "skills required", "first skill", "how to become good", "what should I learn"
  => intent=CAREER_GUIDANCE (NOT SKILL_SEARCH)
- COURSE_DETAILS: details about a specific course title.
- CATEGORY_BROWSE: broad category without skill/topic ("كورسات برمجة", "Programming courses").
- SKILL_SEARCH: learn a specific skill/topic ("عاوز اتعلم Python", "كورسات SQL").
- GREETING/SUPPORT_POLICY/UNSAFE/OUT_OF_SCOPE accordingly.

4) target_categories:
- If in_scope=true: output 1–3 categories from ALLOWED_CATEGORIES (never empty).
- If in_scope=false: empty.

5) keywords:
- 3–10 high-signal terms only.
- exclude Arabic stopwords: عايز، عاوز، اتعلم، تفاصيل، هل، في، عن، ازاي، ايه، اول، ممكن

6) course_title_candidate only for COURSE_DETAILS, else null.
"""

class GroqUnavailableError(Exception):
    pass

def classify_intent(user_question: str) -> RouterOutput:
    q_strip = (user_question or "").strip()
    lang = _detect_lang(q_strip)

    # 1) FOLLOW_UP fast-path (short queries عادة)
    if len(q_strip) <= 40 and _FOLLOW_UP_RE.search(q_strip):
        return RouterOutput(
            in_scope=True,
            intent="FOLLOW_UP",
            target_categories=["General"],
            course_title_candidate=None,
            english_search_term=None,
            goal_role=None,
            keywords=_extract_keywords_fallback(q_strip) or ["more"],
            user_language=lang
        )

    # 2) AVAILABILITY fast-path (مهم جدًا مايتلخبطش)
    if len(q_strip) <= 80 and _AVAIL_RE.search(q_strip):
        # حاول تثبت category من anchors
        cat = _default_category_from_anchors(q_strip)
        return RouterOutput(
            in_scope=True,
            intent="AVAILABILITY_CHECK",
            target_categories=[cat],
            course_title_candidate=None,
            english_search_term=None,
            goal_role=None,
            keywords=_extract_keywords_fallback(q_strip),
            user_language=lang
        )

    client = Groq(api_key=settings.groq_api_key)

    router_input = json.dumps({
        "USER_QUESTION": user_question,
        "ALLOWED_CATEGORIES": ALLOWED_CATEGORIES
    }, ensure_ascii=False)

    max_retries = settings.groq_max_retries
    last_error = None
    content = ""

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
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()

            data = json.loads(content)

            # enforce language fallback
            data["user_language"] = data.get("user_language") or lang

            # normalize categories
            in_scope = bool(data.get("in_scope"))
            cats = data.get("target_categories") or []
            cats = [c for c in cats if c in ALLOWED_CATEGORIES]

            # [FIX] Force in_scope if strong local anchor exists
            # This protects against LLM being too strict or hallucinating scope
            local_cat = _default_category_from_anchors(q_strip)
            if local_cat != "General":
                in_scope = True
                if not cats:
                    cats = [local_cat]

            if in_scope and not cats:
                 if local_cat != "General":
                     cats = [local_cat]
                 else:
                     cats = [_default_category_from_anchors(q_strip)]

            data["target_categories"] = cats if in_scope else []

            # ensure keywords always exist
            kws = data.get("keywords") or []
            if not kws:
                data["keywords"] = _extract_keywords_fallback(q_strip)

            # fill optional fields expected by model (safe)
            data.setdefault("course_title_candidate", None)
            data.setdefault("english_search_term", None)
            data.setdefault("goal_role", None)

            out = RouterOutput(**data)

            logger.info(
                "Router: in_scope=%s intent=%s lang=%s cats=%s kws=%s",
                out.in_scope, out.intent, out.user_language, out.target_categories, out.keywords
            )
            return out

        except json.JSONDecodeError as e:
            logger.error("Router JSON parse failed: %s | raw=%s", str(e), content[:300])

            # deterministic fallback (no LLM)
            cat = _default_category_from_anchors(q_strip)
            
            # career cues fallback (Enriched with AI/DS terms)
            ql = q_strip.lower()
            career_cues = [
                "المهارات المطلوبة","ايه المهارات","ازاي أبقى","ازاي ابقى","أول مهارة","اول مهارة",
                "skills required","first skill","how to become","what should i learn",
                "data scientist","machine learning","ai engineer","عالم بيانات","مهندس ذكاء"
            ]
            if any(cue in q_strip or cue in ql for cue in career_cues):
                return RouterOutput(
                    in_scope=True,
                    intent="CAREER_GUIDANCE",
                    target_categories=[cat],
                    course_title_candidate=None,
                    english_search_term=None,
                    goal_role=None,
                    keywords=_extract_keywords_fallback(q_strip),
                    user_language=lang
                )

            # broad programming fallback
            if any(x in ql for x in ["programming", "coding", "برمجة", "البرمجة"]):
                return RouterOutput(
                    in_scope=True,
                    intent="CATEGORY_BROWSE",
                    target_categories=["Programming"],
                    course_title_candidate=None,
                    english_search_term=None,
                    goal_role=None,
                    keywords=_extract_keywords_fallback(q_strip) or ["programming"],
                    user_language=lang
                )

            # default in-scope skill search if anchors exist
            if cat != "General":
                return RouterOutput(
                    in_scope=True,
                    intent="SKILL_SEARCH",
                    target_categories=[cat],
                    course_title_candidate=None,
                    english_search_term=None,
                    goal_role=None,
                    keywords=_extract_keywords_fallback(q_strip),
                    user_language=lang
                )

            return RouterOutput(
                in_scope=False,
                intent="OUT_OF_SCOPE",
                target_categories=[],
                course_title_candidate=None,
                english_search_term=None,
                goal_role=None,
                keywords=[],
                user_language=lang
            )

        except Exception as e:
            last_error = e
            logger.warning("Router attempt %d failed: %s", attempt + 1, str(e))
            if attempt < max_retries:
                err = str(e).lower()
                if "429" in err or "rate" in err:
                    time.sleep(2 ** attempt)
                    continue
                if err.startswith("5") or "server" in err:
                    time.sleep(1)
                    continue
            break

    raise GroqUnavailableError(f"Router unavailable: {last_error}")
