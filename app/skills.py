"""
skills.py
Module for extracting searchable skills from user input + guidance plan.
Layer 3 of the 7-step pipeline: Extractor.
"""
import logging
import json
from typing import List, Dict, Any
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# 3) SKILL/AREA EXTRACTOR PROMPT (Layer 3)
# ============================================================
SKILL_EXTRACTOR_PROMPT = """You are the Skill & Area Extractor (Stage 2: Identification).

Input:
- user_question
- guidance_plan_areas (list of core areas from Stage 1)
- target_role

Task:
1) Identify ALL relevant skills or professional areas implied by the user's career goal.
2) This is an exploratory stage: do NOT judge whether a skill has courses yet.
3) Convert them into searchable units: canonical_en, label_ar, synonyms, and at least 6 diverse search queries.

Rules:
- Respect Role & Domain Authority: Focus ONLY on skills within the professional domain of the target role.
- Prefer high-level "areas" (e.g. "Cloud Architecture") over narrow tools (e.g. "AWS Console") unless critical.
- Maximum 5 units total.

Return JSON only:
{
  "skills_or_areas": [
    {
      "canonical_en": "string",
      "label_ar": "string",
      "synonyms": ["string"],
      "queries": ["q1", "q2", "q3", "q4", "q5", "q6"]
    }
  ]
}
"""

def extract_skills_and_areas(
    user_question: str,
    guidance_plan_areas: List[Dict],
    target_role: str = None
) -> Dict[str, Any]:
    """
    Layer 3: Extract searchable skills/areas from input + plan.
    """
    client = Groq(api_key=settings.groq_api_key)
    
    # Prepare minimal context for the prompt
    # guidance_plan_areas is expected to be list of core_areas objects from layer 2
    
    input_context = {
        "user_question": user_question,
        "guidance_plan_areas": [a.get("area") for a in guidance_plan_areas if a.get("area")],
        "target_role": target_role
    }

    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SKILL_EXTRACTOR_PROMPT},
                {"role": "user", "content": json.dumps(input_context, ensure_ascii=False)}
            ],
            temperature=0.0,
            max_tokens=1000,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        
        content = completion.choices[0].message.content
        data = json.loads(content)
        return data
        
    except Exception as e:
        logger.error(f"[SkillExtractor] Failed: {e}")
        # Return empty struct so pipeline doesn't crash, 
        # Retrieval will fail naturally if no skills found.
        return {"skills_or_areas": []}

# Backward compatibility alias (if we don't fully refactor chat.py imports immediately)
# But we plan to refactor chat.py, so this is just safety.
analyze_career_request = extract_skills_and_areas 

