"""
Generator module for creating user-facing responses using Groq LLM.
Implements neutral, unbiased guidance with strict RAG grounding.
"""
import json
from groq import Groq
from app.config import settings
from app.router import GroqUnavailableError, ALLOWED_CATEGORIES
import logging

logger = logging.getLogger(__name__)

# Production Generator System Prompt - Neutral & Unbiased
GENERATOR_SYSTEM_PROMPT = """CORE SYSTEM PROMPT — FINAL (Production-Ready)
You are Career Copilot, a production-grade assistant for career guidance and course discovery.

Your behavior must be:
- Neutral
- Conversation-aware
- Non-biased
- Grounded in provided data only

You are NOT a general chatbot.
You do NOT improvise.
You do NOT guess.
You strictly follow the provided SYSTEM STATE and CHAT HISTORY.

--------------------------------------------------
LANGUAGE RULES (STRICT)
--------------------------------------------------
- Always reply in the same language as the user's most recent message.
- Arabic input → Arabic output only.
- English input → English output only.
- Mixed input → respond in the dominant language.
- Never mix languages unless the user explicitly asks.
- Do NOT use religious, political, or cultural phrases unless the user used them first.

--------------------------------------------------
CONVERSATION MEMORY (MANDATORY)
--------------------------------------------------
- You will receive previous messages (CHAT HISTORY).
- You MUST read and use them.
- If the user asks a follow-up (e.g. "طيب ايه أول خطوة", "what next?", "طيب والكورسات؟"):
  continue the same topic from the previous turns.
- Never treat follow-up messages as new unrelated requests.
- Do not reset or restart the conversation unless the user clearly changes the topic.

--------------------------------------------------
NEUTRALITY & NO BIAS
--------------------------------------------------
- Do NOT favor any technology, role, or domain.
- Do NOT introduce new domains unless:
  - the user explicitly mentions them, OR
  - they are explicitly present in SYSTEM STATE routing.
- Do NOT say something is “required” unless it truly is.
- Do NOT add assumptions about the user’s level or background.

--------------------------------------------------
CATALOG & DATA GROUNDING
--------------------------------------------------
- You may ONLY mention courses provided in SYSTEM STATE catalog_context.results.
- NEVER invent course titles, instructors, levels, categories, or examples.
- NEVER use placeholders.

--------------------------------------------------
NEGATIVE CONSTRAINTS (STRICT)
--------------------------------------------------
- You must NEVER mention external platforms (e.g., Coursera, Udemy, EdX, YouTube, Codecademy).
- You must NEVER tell the user to "search online" or "visit other websites".
- If a course is not in the catalog, DO NOT suggest looking elsewhere.
- General advice must be abstract concepts only (e.g., "Learn Python syntax") without naming platform sources.

--------------------------------------------------
CASE HANDLING
--------------------------------------------------
- If no courses found:
  Say: "I couldn't find matching courses in our catalog."
  Then: Ask a clarification question or offer general conceptual advice (without external links).

--------------------------------------------------
OUTPUT STYLE (CHATGPT-LIKE, CLEAN)
--------------------------------------------------
- Plain text only.
- NO markdown (** ### ```).
- NO technical labels like:
  "SKILLS:", "NEXT STEPS:", "COURSES:", "QUESTION:"
- Organize the response into clear sections using natural language.
- Separate sections with a blank line.
- Use short paragraphs.
- You MAY use 1–2 light emojis if they improve readability.
- If listing courses, list ONE course per line in this exact format:
  Course Title — Level — Category — Instructor

--------------------------------------------------
INTENT BEHAVIOR
--------------------------------------------------
- GREETING:
  Short greeting + ask how you can help.

- CAREER_GUIDANCE:
  Practical, focused advice related to the current conversation topic.
  If courses exist, list them.
  End with ONE clarifying question only.

- SEARCH:
  Focus on listing courses.
  If none exist, ask ONE clarifying question.

- COURSE_DETAILS:
  Provide factual details only from the catalog.

- PLAN_REQUEST:
  Provide a simple outline.
  Do NOT invent courses.

- OUT_OF_SCOPE:
  Politely refuse and mention examples of allowed domains.

- UNSAFE:
  Refuse briefly and clearly.

--------------------------------------------------
FINAL RULE
--------------------------------------------------
Before answering, silently verify:
- I used conversation history.
- I stayed neutral and on-topic.
- I did not invent data.
- My formatting is clean and readable.

If any of these fail, fix the answer before responding."""


def generate_response(
    user_question: str,
    in_scope: bool,
    intent: str,
    target_categories: list,
    catalog_results: list = None,
    suggested_titles: list = None,
    user_language: str = "ar",
    chat_history: list = None
) -> str:
    """
    Generate final user-facing response using Groq LLM.
    
    Args:
        user_question: Original user question
        in_scope: Whether question is within catalog scope
        intent: Classified intent
        target_categories: Matched categories
        catalog_results: Retrieved courses (list of Course objects)
        suggested_titles: Alternative titles if exact match not found
        user_language: Detected user language (en/ar/mixed)
        chat_history: List of previous messages (dics with role/content)
        
    Returns:
        Generated response text
        
    Raises:
        GroqUnavailableError: If Groq API unavailable
    """
    from app.system_state import build_system_state
    from app.models import RouterOutput
    
    client = Groq(api_key=settings.groq_api_key)
    
    # Prepare catalog context
    catalog_results = catalog_results or []
    suggested_titles = suggested_titles or []
    chat_history = chat_history or []
    
    # Handle GREETING intent with simple response (no LLM call needed)
    if intent == "GREETING":
        if user_language == "ar":
            greetings = [
                "أهلاً! أنا مساعدك للتوجيه المهني. إزاي أقدر أساعدك؟",
                "مرحباً! أنا هنا عشان أساعدك تختار الكورسات المناسبة. إيه اللي محتاجه؟",
                "أهلاً وسهلاً! قولي إزاي أقدر أساعدك في مسارك المهني؟"
            ]
        else:
            greetings = [
                "Hello! I'm your career guidance assistant. How can I help you?",
                "Hi there! I'm here to help you find the right courses. What are you looking for?",
                "Hey! Ready to help with your career journey. What would you like to learn?"
            ]
        import random
        return random.choice(greetings)
    
    # Build RouterOutput for system state
    router_output = RouterOutput(
        in_scope=in_scope,
        intent=intent,
        target_categories=target_categories,
        user_language=user_language
    )
    
    # Build authoritative SYSTEM STATE envelope
    system_state_block = build_system_state(
        routing=router_output,
        catalog_results=catalog_results,
        results_count=len(catalog_results),
        suggested_titles=suggested_titles
    )
    
    # Prepare messages payload (Production Structure)
    messages_payload = [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "system", "content": system_state_block}
    ]
    
    # Append real chat history turns
    if chat_history:
        messages_payload.extend(chat_history)
        
    # Append current user question
    messages_payload.append({"role": "user", "content": user_question})
    
    # Log results_count server-side for RAG validation
    logger.info(f"Generator called: in_scope={in_scope}, intent={intent}, user_language={user_language}, results_count={len(catalog_results)}")
    
    # Retry logic
    max_retries = settings.groq_max_retries
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages_payload,
                temperature=0.5,  # Lower for more consistent outputs
                max_tokens=800,
                timeout=settings.groq_timeout_seconds
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info(f"Generator produced {len(answer)} chars")
            return answer
            
        except Exception as e:
            last_error = e
            logger.warning(f"Generator attempt {attempt + 1} failed: {str(e)}")
            
            # Retry logic
            if attempt < max_retries:
                if "429" in str(e) or "rate" in str(e).lower():
                    import time
                    time.sleep(2 ** attempt)
                    continue
                elif "5" in str(e)[:3]:
                    import time
                    time.sleep(1)
                    continue
            
            break
    
    # If all retries fail
    logger.error(f"Generator failed after {max_retries + 1} attempts: {last_error}")
    raise GroqUnavailableError(f"Generator unavailable: {last_error}")
