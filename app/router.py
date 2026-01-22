"""
Router module for intent classification using Groq LLM.
Implements scope-gated routing with allowed categories.
"""
import json
from groq import Groq
from app.config import settings
from app.models import RouterOutput
import logging

logger = logging.getLogger(__name__)

# Allowed categories from catalog
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

# Scope Router System Prompt - PRODUCTION (JSON-only)
ROUTER_SYSTEM_PROMPT = """You are the ROUTER for Career Copilot. Return JSON ONLY. Do not answer the user.

You will receive:
- USER_QUESTION (string)
- ALLOWED_CATEGORIES (list of strings, exact)

Your job:
1) Detect user_language: "en" | "ar" | "mixed"
2) Decide in_scope:
   - in_scope=true if the user's request maps to any ALLOWED_CATEGORIES or common synonyms of them
     (examples: leadership, management, time management, communication, negotiation, sales, programming, cybersecurity, web, mobile, marketing, HR, banking, project management, etc.)
   - in_scope=false if the topic is clearly unrelated and does not map (e.g., cooking, acting, sports news, movie recommendations).
3) Choose intent:
   - COURSE_DETAILS: user asks about a specific course title OR asks instructor/level/category/description for a named course
   - SEARCH: user wants browsing courses by category/level/topic keywords
   - CAREER_GUIDANCE: user wants advice to become better at an in-scope role/skill, without a time-based schedule
   - PLAN_REQUEST: user explicitly asks for a plan/roadmap/schedule (e.g., 30-day, 8 weeks, weekly plan)
   - SUPPORT_POLICY: pricing/subscription/refund/certificates/payment/support
   - UNSAFE: hacking/piracy/malware/stealing
   - OUT_OF_SCOPE: unrelated to our domains

4) Output 1–3 target_categories (must be items from ALLOWED_CATEGORIES).
5) Output 3–10 keywords for retrieval. Do not include Arabic stopwords:
   (اللي، ده، دي، بنفس، اسمه، عنوانه، عن، في، هل، ممكن، عاوز، عايز، ورّيني، هات، تفاصيل)

Rules:
- If uncertain, choose in_scope=false.
- Never output anything other than JSON.

Return JSON:
{
  "user_language": "en|ar|mixed",
  "in_scope": true,
  "intent": "COURSE_DETAILS|SEARCH|CAREER_GUIDANCE|PLAN_REQUEST|SUPPORT_POLICY|UNSAFE|OUT_OF_SCOPE",
  "target_categories": [],
  "keywords": [],
  "course_title_candidate": null
}"""


class GroqUnavailableError(Exception):
    """Raised when Groq API is unavailable after retries."""
    pass


def classify_intent(user_question: str) -> RouterOutput:
    """
    Classify user intent using Groq LLM with scope gating.
    
    Args:
        user_question: Raw user message
        
    Returns:
        RouterOutput with scope and intent classification
        
    Raises:
        GroqUnavailableError: If Groq API fails after retries
    """
    client = Groq(api_key=settings.groq_api_key)
    
    # Build JSON input as per production spec
    router_input = json.dumps({
        "USER_QUESTION": user_question,
        "ALLOWED_CATEGORIES": ALLOWED_CATEGORIES
    }, ensure_ascii=False)
    
    # Retry logic
    max_retries = settings.groq_max_retries
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": router_input}
                ],
                temperature=0.0,  # Deterministic routing
                max_tokens=400,
                timeout=settings.groq_timeout_seconds,
                response_format={"type": "json_object"}  # Enforce JSON output
            )
            
            # Parse JSON response
            content = response.choices[0].message.content.strip()
            
            # Handle potential markdown code blocks (fallback)
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            router_data = json.loads(content)
            
            # Validate and return
            router_output = RouterOutput(**router_data)
            logger.info(f"Router classified: in_scope={router_output.in_scope}, intent={router_output.intent}, lang={router_output.user_language}")
            return router_output
            
        except json.JSONDecodeError as e:
            logger.error(f"Router returned invalid JSON: {content}")
            last_error = e
            # Fall back to in-scope SEARCH intent on parse error
            return RouterOutput(
                in_scope=True,
                intent="SEARCH",
                keywords=[user_question[:50]],
                user_language="ar"
            )
            
        except Exception as e:
            last_error = e
            logger.warning(f"Router attempt {attempt + 1} failed: {str(e)}")
            
            # Check if we should retry
            if attempt < max_retries:
                if "429" in str(e) or "rate" in str(e).lower():
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                elif "5" in str(e)[:3]:  # 5xx server errors
                    import time
                    time.sleep(1)
                    continue
            
            # If all retries exhausted
            break
    
    # If all retries fail
    logger.error(f"Router failed after {max_retries + 1} attempts: {last_error}")
    raise GroqUnavailableError(f"Router unavailable: {last_error}")
