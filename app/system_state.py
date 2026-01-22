"""
Production System State Envelope for Career Copilot RAG.
Builds authoritative SYSTEM STATE block sent with every LLM call.

This module ensures:
- Explicit language policy enforcement
- Scope policy with allowed categories
- RAG context grounding
- Non-negotiable hard rules
"""
import json
from datetime import datetime, timezone
from typing import List, Optional, Any
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
    Truncates descriptions for token efficiency.
    """
    catalog_items = []
    for course in courses[:10]:  # Limit to 10 courses
        catalog_items.append({
            "title": course.title,
            "level": course.level,
            "category": course.category,
            "instructor": course.instructor,
            "duration_hours": float(course.duration_hours) if course.duration_hours else None,
            "description": course.description[:200] if course.description else None
        })
    return catalog_items


def build_system_state(
    routing: RouterOutput,
    catalog_results: List[CourseSchema],
    results_count: Optional[int] = None
) -> str:
    """
    Build authoritative SYSTEM STATE envelope for LLM calls.
    
    Args:
        routing: Router output with intent, scope, and language info
        catalog_results: Retrieved courses from catalog
        results_count: Number of results (defaults to len(catalog_results))
        
    Returns:
        Formatted SYSTEM STATE block as string
    """
    if results_count is None:
        results_count = len(catalog_results)
    
    # Build catalog context
    catalog_context = build_catalog_context(catalog_results)
    
    # Build the authoritative system state
    system_state = f"""=== SYSTEM STATE (AUTHORITATIVE) ===
product: "Career Copilot"
date_utc: "{datetime.now(timezone.utc).isoformat()}"

language_policy:
  - Always reply in the same language as the user's last message.
  - If the user mixes languages, reply in the dominant language, unless the user explicitly asks otherwise.
  - Never switch languages unexpectedly.

scope_policy:
  allowed_categories: {json.dumps(ALLOWED_CATEGORIES, ensure_ascii=False)}

routing:
  in_scope: {str(routing.in_scope).lower()}
  intent: "{routing.intent}"
  target_categories: {json.dumps(routing.target_categories, ensure_ascii=False)}
  user_language: "{routing.user_language}"

catalog_context:
  results_count: {results_count}
  results: {json.dumps(catalog_context, ensure_ascii=False, indent=2)}

hard_rules:
  - Treat SYSTEM STATE as ground truth. If your answer contradicts it, your answer is WRONG.
  - Never invent course titles or course details. Only mention courses present in catalog_context.results.
  - If catalog_context.results is empty, you may still give general advice (only if in_scope=true), but you must not list courses.
  - If in_scope=false, refuse politely and do not provide advice outside our domains.

=== END SYSTEM STATE ==="""
    
    logger.debug(f"Built system state: in_scope={routing.in_scope}, intent={routing.intent}, results={results_count}")
    return system_state


def get_allowed_categories() -> List[str]:
    """Return the list of allowed categories for the scope policy."""
    return ALLOWED_CATEGORIES.copy()
