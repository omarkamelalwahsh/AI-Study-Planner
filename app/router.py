"""
router.py
Router module for intent classification using Groq LLM.
Implements scope-gated routing with allowed categories + follow-up intent.
"""
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

# quick local follow-up detector (works even if LLM fails)
_FOLLOW_UP_RE = re.compile(r"^(هل\s+في\s+غيرهم|هل\s+في\s+غيره|هل\s+في\s+كمان|في\s+غيرهم|في\s+غيره|في\s+كمان|غيرهم|غيره|كمان|more|any\s+more|show\s+more)\??\.?$", re.IGNORECASE)

_ROUTER_SYSTEM_PROMPT = """You are the ROUTER for Career Copilot. Return JSON ONLY. Do not answer the user.

You receive:
- USER_QUESTION
- ALLOWED_CATEGORIES (exact list)

Tasks:
1) user_language: "en" | "ar" | "mixed"

2) in_scope:
- true if the query maps to allowed categories OR strong anchors
- false only if clearly unrelated

STRONG ANCHORS (deterministic):
- Programming: python, java, c++, c#, javascript, typescript, coding, programming, بايثون
- Web Development: html, css, react, node, frontend, backend, web
- Mobile Development: android, ios, kotlin, swift, flutter
- Data Security: cybersecurity, security, privacy
- Networking: network, tcp, ccna
- Project Management: scrum, agile, PMP
- Career Development: resume, cv, interview, portfolio
- Technology Applications: excel, powerpoint, word

If ANY anchor appears => in_scope=true.

3) intent (choose exactly one):
- GREETING
- COURSE_DETAILS (asks details for a specific named course title)
- SKILL_SEARCH (asks to learn a skill like Python/SQL, or "كورسات بايثون")
- CATEGORY_BROWSE (asks about a category like "Programming courses" without specifying skill/topic)
- AVAILABILITY_CHECK (asks "Do you have courses for X?" / "هل عندكم كورسات ...؟")
- FOLLOW_UP (asks for more: "هل في غيرهم؟", "show more", "any more")
- CAREER_GUIDANCE (general advice within scope; not schedule)
- PLAN_REQUEST (asks for roadmap/schedule/timeframe)
- SUPPORT_POLICY
- UNSAFE
- OUT_OF_SCOPE

4) target_categories:
- If in_scope=true: output 1–3 categories from ALLOWED_CATEGORIES (never empty).
- If in_scope=false: empty.

5) keywords (3–10):
- high-signal terms only; exclude Arabic stopwords (عايز، عاوز، اتعلم، تفاصيل، هل، في، عن...)

6) course_title_candidate: only for COURSE_DETAILS if user provided a specific title.

Return JSON:
{
  "user_language": "en|ar|mixed",
  "in_scope": true,
  "intent": "GREETING|COURSE_DETAILS|SKILL_SEARCH|CATEGORY_BROWSE|AVAILABILITY_CHECK|FOLLOW_UP|CAREER_GUIDANCE|PLAN_REQUEST|SUPPORT_POLICY|UNSAFE|OUT_OF_SCOPE",
  "target_categories": [],
  "keywords": [],
  "course_title_candidate": null
}
"""

class GroqUnavailableError(Exception):
    pass


def _detect_lang(q: str) -> str:
    has_ar = bool(re.search(r"[\u0600-\u06FF]", q or ""))
    has_en = bool(re.search(r"[A-Za-z]", q or ""))
    if has_ar and has_en:
        return "mixed"
    if has_ar:
        return "ar"
    return "en"


def classify_intent(user_question: str) -> RouterOutput:
    # local fast-path for follow-up
    if _FOLLOW_UP_RE.match((user_question or "").strip()):
        return RouterOutput(
            user_language=_detect_lang(user_question),
            in_scope=True,
            intent="FOLLOW_UP",
            target_categories=["General"],
            keywords=["more", "additional"],
            course_title_candidate=None
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
                max_tokens=400,
                timeout=settings.groq_timeout_seconds,
                response_format={"type": "json_object"}
            )

            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()

            data = json.loads(content)

            assumed_lang = data.get("user_language") or _detect_lang(user_question)
            data["user_language"] = assumed_lang

            # normalize categories
            cats = data.get("target_categories") or []
            cats = [c for c in cats if c in ALLOWED_CATEGORIES]
            in_scope = bool(data.get("in_scope"))

            if in_scope and not cats:
                # safe deterministic default
                ql = (user_question or "").lower()
                if any(x in ql for x in ["python", "بايثون", "program", "coding", "java", "c++", "javascript"]):
                    cats = ["Programming"]
                elif any(x in ql for x in ["web", "html", "css", "react", "frontend", "backend"]):
                    cats = ["Web Development"]
                else:
                    cats = ["General"]

            data["target_categories"] = cats if in_scope else []

            out = RouterOutput(**data)
            logger.info(
                "Router: in_scope=%s intent=%s lang=%s cats=%s kws=%s",
                out.in_scope, out.intent, out.user_language, out.target_categories, out.keywords
            )
            return out

        except json.JSONDecodeError as e:
            logger.error("Router JSON parse failed: %s | raw=%s", str(e), content[:300])
            # fallback: try anchors
            ql = (user_question or "").lower()
            if any(x in ql for x in ["python", "بايثون", "program", "coding", "java", "c++", "javascript"]):
                return RouterOutput(
                    user_language=_detect_lang(user_question),
                    in_scope=True,
                    intent="SKILL_SEARCH",
                    target_categories=["Programming"],
                    keywords=["python", "beginner", "programming"],
                    course_title_candidate=None
                )
            return RouterOutput(
                user_language=_detect_lang(user_question),
                in_scope=False,
                intent="OUT_OF_SCOPE",
                target_categories=[],
                keywords=[],
                course_title_candidate=None
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
