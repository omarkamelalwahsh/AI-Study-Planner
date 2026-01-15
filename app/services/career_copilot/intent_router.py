import logging
import re
from typing import Optional, Dict, Any
from app.schemas_career import UserIntent
from app.search.embedding import normalize_ar

logger = logging.getLogger(__name__)

class IntentRouter:
    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect user language: ar | en | mixed | other.
        """
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if arabic_chars > 0 and english_chars > 0:
            return "mixed"
        elif arabic_chars > 0:
            return "ar"
        else:
            return "en"

    @staticmethod
    def parse_intent(message: str, history: Optional[list] = None) -> UserIntent:
        """
        STEP 2 — INTENT UNDERSTANDING
        Extract structured intent: career_goal, sector, constraints, confidence_level.
        """
        normalized = normalize_ar(message)
        lang = IntentRouter.detect_language(message)
        
        # Detect confidence level (vague vs clear)
        # Vague if message lacks a specific role from our patterns or uses broad sector terms
        words = message.split()
        
        # Check if any specific role is matched
        role_matched = False
        role_patterns = {
            "Software Engineer": ["برمجة", "programming", "developer", "مهندس"],
            "Data Analyst": ["data", "بيانات", "تحليل"],
            "Manager": ["manager", "مدير", "ادارة"],
            "AI Professional": ["ai", "ذكاء اصطناعي", "artificial intelligence"]
        }
        
        for role, keywords in role_patterns.items():
            if any(kw in normalized or kw in message.lower() for kw in keywords):
                role_matched = True
                break
        
        is_vague = not role_matched or len(words) < 5 or "tech" in message.lower() or "مجال" in normalized
        # print(f"DEBUG: role_matched={role_matched}, words_len={len(words)}, tech_in={'tech' in message.lower()}, is_vague={is_vague}")
        
        intent = UserIntent(
            query=message,
            language=lang,
            confidence_level="vague" if is_vague else "clear",
            is_career_related=True
        )
        
        # Simple extraction logic for demonstration
        # In production, this would be an LLM call.
        role_patterns = {
            "Software Engineer": ["برمجة", "programming", "developer", "مهندس"],
            "Data Analyst": ["data", "بيانات", "تحليل"],
            "Manager": ["manager", "مدير", "ادارة"],
            "AI Professional": ["ai", "ذكاء اصطناعي", "artificial intelligence"]
        }
        
        for role, keywords in role_patterns.items():
            if any(kw in normalized or kw in message.lower() for kw in keywords):
                intent.career_goal = role
                break
        
        return intent
