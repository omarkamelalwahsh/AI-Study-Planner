import re
import logging
import json
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

# Basic in-memory store for session contexts
_SESSIONS: Dict[str, "SessionContext"] = {}

FOLLOWUP_PATTERNS = [
    r"في كمان", r"غيرها", r"غير دول", r"غير ده", r"افكار تانية",
    r"more", r"more ideas", r"anything else", r"projects more",
    r"next", r"harder", r"advanced", r"أصعب", r"أسهل", 
    r"beginner", r"easier", r"مبتدئ", r"another"
]

class SessionContext(BaseModel):
    session_id: str
    last_topic: Optional[str] = None
    last_role_type: Optional[str] = None
    last_level: Optional[str] = "Beginner"
    last_skills: List[str] = []
    exposed_projects: Set[str] = set() # Stores "Level:Title" to avoid dupes

    class Config:
        arbitrary_types_allowed = True

def get_session_context(session_id: str) -> SessionContext:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = SessionContext(session_id=session_id)
    return _SESSIONS[session_id]

def update_session_context(session_id: str, topic: str, role_type: str, projects: List[Dict], skills: List[str] = []):
    ctx = get_session_context(session_id)
    if topic:
        ctx.last_topic = topic
    if role_type:
        ctx.last_role_type = role_type
    
    # Update skills if provided, otherwise keep old ones (context persistence)
    if skills:
        ctx.last_skills = skills

    # Track exposed projects
    for p in projects:
        # Robustly handle p being dict or object
        if isinstance(p, dict):
            key = f"{p.get('level')}:{p.get('title')}"
        else:
            key = f"{getattr(p, 'level', '')}:{getattr(p, 'title', '')}"
        ctx.exposed_projects.add(key)
    
    _SESSIONS[session_id] = ctx

# Export for Router
FOLLOW_UP_RE = re.compile(r"|".join(FOLLOWUP_PATTERNS), re.IGNORECASE)

class FollowupManager:
    @staticmethod
    def is_followup(message: str) -> bool:
        """Detects if the user is asking for 'more' or 'others' using patterns."""
        msg = message.lower().strip()
        # Check specific patterns
        if FOLLOW_UP_RE.search(msg):
            return True
        return False

    @staticmethod
    def infer_requested_level(message: str) -> Optional[str]:
        """Infers the requested difficulty level from the message."""
        msg = message.lower()
        if any(w in msg for w in ["beginner", "مبتدئ", "أسهل", "easier", "simple", "easy"]):
            return "Beginner"
        if any(w in msg for w in ["intermediate", "متوسط", "medium"]):
            return "Intermediate"
        if any(w in msg for w in ["advanced", "متقدم", "أصعب", "harder", "complex", "pro"]):
            return "Advanced"
        return None

    @staticmethod
    def should_rerun_retrieval(message: str, session_id: str) -> bool:
        """
        Decide whether to re-run retrieval or continue from context.
        If it's a follow-up ("more projects") and we have a topic, return FALSE (skip retrieval).
        """
        ctx = get_session_context(session_id)
        if ctx.last_topic and FollowupManager.is_followup(message):
            logger.info(f"Followup Manager: Detected follow-up for topic '{ctx.last_topic}'. Skipping retrieval.")
            return False
        return True

def generate_dynamic_projects(session_id: str, requested_level: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate NEW project ideas using LLM based on context.
    Respects requested level if provided (e.g. "Harder").
    """
    ctx = get_session_context(session_id)
    topic = ctx.last_topic or "General Career"
    skills = ctx.last_skills or []
    
    # Determine level strategy
    effective_level = requested_level or ctx.last_level or "Intermediate"
    level_instruction = f"Focus strictly on {effective_level} level projects." if requested_level else "Vary difficulty (Beginner -> Advanced)."

    # Prepare list of already shown projects to explicitly forbid them
    shown_list = list(ctx.exposed_projects)
    shown_text = "\n".join(shown_list[-20:]) if shown_list else "None"

    system_prompt = f"""You are a Senior Career Mentor and Practical Learning Designer.

Your task is to generate 3 NEW practical project ideas for:
- Topic: {topic}
- Skills: {", ".join(skills)}

CONTEXT:
- Previously Shown Projects (DO NOT REPEAT):
{shown_text}

{level_instruction}

STRICT RULES:
1. Projects must be realistic and practice-oriented.
2. Do NOT repeat titles from the list above.
3. If the user asked for "Harder", give complex system-design or full-stack ideas.
4. If "Easier", give isolated scripts or simple tools.

OUTPUT FORMAT (JSON ONLY):
{{
    "projects": [
        {{
            "title": "...",
            "level": "Beginner/Intermediate/Advanced",
            "description": "...",
            "skills": ["Skill1", "Skill2"]
        }}
    ]
}}
"""
    
    client = Groq(api_key=settings.groq_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7, 
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        new_projects = data.get("projects", [])
        
        # Update context
        update_session_context(session_id, topic, ctx.last_role_type or "general", new_projects, skills)
        
        return new_projects
    except Exception as e:
        logger.error(f"Failed to generate dynamic projects: {e}")
        return []
