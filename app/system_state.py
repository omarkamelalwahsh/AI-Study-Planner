"""
system_state.py
Production System State Envelope for Career Copilot RAG.
Authoritative JSON block for LLM calls, including session memory for follow-ups.
"""
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.models import RouterOutput, CourseSchema
import logging

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = [
    "Banking Skills","Business Fundamentals","Career Development",
    "Creativity and Innovation","Customer Service","Data Security",
    "Digital Media","Disaster Management and Preparedness",
    "Entrepreneurship","Ethics and Social Responsibility","Game Design",
    "General","Graphic Design","Health & Wellness","Human Resources",
    "Leadership & Management","Marketing Skills","Mobile Development",
    "Networking","Personal Development","Programming","Project Management",
    "Public Speaking","Sales","Soft Skills","Sustainability",
    "Technology Applications","Web Development"
]

def build_catalog_context(courses: List[CourseSchema]) -> List[dict]:
    items = []
    for c in courses[:10]:
        desc = None
        if c.description:
            desc = c.description[:250].replace("\n", " ").replace("\r", " ").strip()

        items.append({
            "course_id": str(c.course_id),
            "title": c.title,
            "level": c.level,
            "category": c.category,
            "instructor": c.instructor,
            "duration_hours": float(c.duration_hours) if c.duration_hours else None,
            "skills": (c.skills[:250] if c.skills else None),
            "description": desc
        })
    return items

def build_system_state(
    routing: RouterOutput,
    catalog_results: List[CourseSchema],
    results_count: Optional[int] = None,
    suggested_titles: Optional[List[str]] = None,
    session_memory: Optional[Dict[str, Any]] = None
) -> str:
    if results_count is None:
        results_count = len(catalog_results)

    catalog_context = build_catalog_context(catalog_results)

    mem = session_memory or {}
    mem.setdefault("last_skill_query", None)          # e.g. "python"
    mem.setdefault("last_categories", [])             # e.g. ["Programming"]
    mem.setdefault("offset", 0)
    mem.setdefault("page_size", 5)

    obj = {
        "product": "Career Copilot",
        "date_utc": datetime.now(timezone.utc).isoformat(),

        "language_policy": {
            "rule": "Reply in the same language as the user's last message.",
            "mixed_rule": "If mixed, reply in the dominant language unless the user asks otherwise.",
            "no_language_switch": True
        },

        "scope_policy": {"allowed_categories": ALLOWED_CATEGORIES},

        "routing": {
            "in_scope": routing.in_scope,
            "intent": routing.intent,
            "target_categories": routing.target_categories,
            "user_language": routing.user_language
        },

        "session_memory": mem,

        "catalog_context": {
            "total_results_count": results_count,
            "returned_results_count": len(catalog_context),
            "results": catalog_context,
            "suggested_alternatives": suggested_titles or []
        },

        "output_policy": {
            "format": "json_object",
            "schema_owner": "generator",
            "max_courses_to_list": 5,
            "one_course_per_paragraph": True
        },

        "hard_rules": [
            "Treat SYSTEM STATE as ground truth.",
            "Never invent course titles or details.",
            "Mention ONLY courses present in catalog_context.results.",

            # Follow-up rule
            "If routing.intent is FOLLOW_UP: continue the same skill/topic using session_memory.last_skill_query and session_memory.offset.",

            # Category browsing rule
            "If routing.intent is CATEGORY_BROWSE: do NOT list courses. Ask ONE question to narrow down (skill/topic or level).",

            # Skill search rule
            "If routing.intent is SKILL_SEARCH or SEARCH: list up to session_memory.page_size courses and include short description + key skills if available.",

            # availability check
            "If routing.intent is AVAILABILITY_CHECK: reply with whether courses exist in the catalog for the request. If yes, ask if the user wants to see them now.",

            # search with 0 results
            "If routing.intent is SKILL_SEARCH or SEARCH and catalog_context.returned_results_count is 0: set mode=NO_DATA and state there are no matching courses currently.",

            # career guidance with 0 results
            "If routing.intent is CAREER_GUIDANCE and catalog_context.returned_results_count is 0: you may provide general guidance but MUST NOT list courses.",

            "NEGATIVE CONSTRAINT: Never mention external platforms (Coursera, Udemy, etc.).",
            "NEGATIVE CONSTRAINT: Never imply the user should search elsewhere."
        ]
    }

    state = (
        "=== SYSTEM STATE (AUTHORITATIVE JSON) ===\n"
        + json.dumps(obj, ensure_ascii=False, indent=2)
        + "\n=== END SYSTEM STATE ==="
    )

    logger.debug("system_state built intent=%s returned=%d", routing.intent, len(catalog_context))
    return state
