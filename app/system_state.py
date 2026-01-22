"""
Production System State Envelope for Career Copilot RAG.
Builds authoritative JSON SYSTEM STATE block sent with every LLM call.

This module ensures:
- Explicit language policy enforcement
- Scope policy with allowed categories
- RAG context grounding
- Non-negotiable hard rules
- Neutral, unbiased behavior
"""
import json
from datetime import datetime, timezone
from typing import List, Optional
from app.models import RouterOutput, CourseSchema
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Allowed Categories (Scope Policy)
# ============================================================
ALLOWED_CATEGORIES = [
    "Banking Skills",
    "Business Fundamentals",
    "Career Development",
    "Creativity and Innovation",
    "Customer Service",
    "Data Security",
    "Digital Media",
    "Disaster Management and Preparedness",
    "Entrepreneurship",
    "Ethics and Social Responsibility",
    "Game Design",
    "General",
    "Graphic Design",
    "Health & Wellness",
    "Human Resources",
    "Leadership & Management",
    "Marketing Skills",
    "Mobile Development",
    "Networking",
    "Personal Development",
    "Programming",
    "Project Management",
    "Public Speaking",
    "Sales",
    "Soft Skills",
    "Sustainability",
    "Technology Applications",
    "Web Development"
]


def build_catalog_context(courses: List[CourseSchema]) -> List[dict]:
    """
    Build catalog context array from course schemas.
    Includes all relevant fields for neutral presentation.
    """
    catalog_items = []
    for course in courses[:10]:  # Limit to 10 courses
        # Clean description (remove newlines)
        description = None
        if course.description:
            description = course.description[:200].replace('\n', ' ').replace('\r', ' ').strip()
        
        catalog_items.append({
            "course_id": str(course.course_id),
            "title": course.title,
            "level": course.level,
            "category": course.category,
            "instructor": course.instructor,
            "duration_hours": float(course.duration_hours) if course.duration_hours else None,
            "skills": course.skills[:200] if course.skills else None,
            "cover": course.cover,
            "description": description
        })
    return catalog_items


def build_system_state(
    routing: RouterOutput,
    catalog_results: List[CourseSchema],
    results_count: Optional[int] = None,
    suggested_titles: Optional[List[str]] = None
) -> str:
    """
    Build authoritative JSON SYSTEM STATE envelope for LLM calls.
    
    Args:
        routing: Router output with intent, scope, and language info
        catalog_results: Retrieved courses from catalog
        results_count: Number of results (defaults to len(catalog_results))
        
    Returns:
        Formatted JSON SYSTEM STATE block as string
    """
    if results_count is None:
        results_count = len(catalog_results)
    
    # Build catalog context
    catalog_context = build_catalog_context(catalog_results)
    
    # Build the authoritative JSON system state
    system_state_obj = {
        "product": "Career Copilot",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        
        "language_policy": {
            "rule": "Reply in the same language as the user's last message.",
            "mixed_rule": "If mixed, reply in the dominant language unless the user asks otherwise.",
            "no_language_switch": True
        },
        
        "scope_policy": {
            "allowed_categories": ALLOWED_CATEGORIES
        },
        
        "routing": {
            "in_scope": routing.in_scope,
            "intent": routing.intent,
            "target_categories": routing.target_categories,
            "user_language": routing.user_language
        },
        
        "catalog_context": {
            "total_results_count": results_count,
            "returned_results_count": len(catalog_context),
            "results": catalog_context,
            "suggested_alternatives": suggested_titles or []
        },
        
        "output_policy": {
            "plain_text_only": True,
            "no_markdown": True,
            "no_section_labels": ["SKILLS:", "NEXT STEPS:", "COURSES:", "QUESTION:"],
            "paragraph_spacing": "Use blank lines between paragraphs.",
            "courses_one_per_line": True,
            "max_courses_to_list": 8
        },
        
        "hard_rules": [
            "Treat SYSTEM STATE as ground truth.",
            "Never invent course titles or course details.",
            "You may mention ONLY courses present in catalog_context.results.",
            "If routing.in_scope is false: refuse politely and do not provide advice outside allowed categories.",
            "If routing.intent is SEARCH and catalog_context.returned_results_count is 0: do not give general advice; ask one clarification question.",
            "If routing.intent is CAREER_GUIDANCE and catalog_context.returned_results_count is 0: you may give general advice but must not list courses.",
            "NEGATIVE CONSTRAINT: You must NEVER mention external platforms (e.g., Coursera, Udemy, EdX, YouTube).",
            "NEGATIVE CONSTRAINT: You must NEVER imply that the user should search elsewhere."
        ]
    }
    
    system_state = f"""=== SYSTEM STATE (AUTHORITATIVE JSON) ===
{json.dumps(system_state_obj, ensure_ascii=False, indent=2)}
=== END SYSTEM STATE ==="""
    
    logger.debug(f"Built system state: in_scope={routing.in_scope}, intent={routing.intent}, results={results_count}")
    return system_state


def get_allowed_categories() -> List[str]:
    """Return the list of allowed categories for the scope policy."""
    return ALLOWED_CATEGORIES.copy()
