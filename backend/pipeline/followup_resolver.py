"""
Career Copilot RAG Backend - Follow-up Resolver
Handles state-based conversations:
1. Pending Questions (Yes/No, Numeric, Choices)
2. One Question Follow-ups (Choice Selection)
3. Pagination / "Show More" requests
"""
import logging
from typing import Optional, Dict, Any
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

class FollowupResolver:
    def __init__(self):
        pass

    def resolve(self, message: str, session_state: Dict[str, Any], intent_type: Optional[IntentType] = None) -> Optional[IntentResult]:
        """
        Main entry point for follow-up resolution.
        Checks for pending questions first, then handles 'More' requests.
        """
        raw_msg = (message or "").strip()
        msg_clean = raw_msg.lstrip("-•* ").strip()
        msg_lower = msg_clean.lower()
        
        # 1. Handle "Pending Question" (Structured flows)
        pending = session_state.get("pending_question")
        if pending:
             res = self._resolve_pending(pending, msg_lower, msg_clean, session_state)
             if res:
                 session_state["pending_question"] = None
                 return res

        # 2. Handle "Last One Question"
        last_q = session_state.get("last_one_question")
        if last_q:
            res = self._resolve_one_question(last_q, msg_lower, msg_clean, match_original=raw_msg)
            if res:
                session_state["last_one_question"] = None
                return res
        
        # 3. Handle Pagination / "Show More"
        is_implicit_more = any(t in msg_lower for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        if intent_type == IntentType.FOLLOW_UP or is_implicit_more:
            return self._handle_pagination(session_state)

        # 4. Contextual "Show"
        show_words = {"اعرض", "وريني", "show", "عرض"}
        if any(w in msg_lower for w in show_words):
            last_topic = session_state.get("last_topic")
            if last_topic:
                 return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=last_topic,
                    needs_courses=True,
                    confidence=0.95
                )

        return None

    def _handle_pagination(self, session_state: Dict[str, Any]) -> IntentResult:
        """Logic for offset-based pagination and course deduplication."""
        cached_ids = session_state.get("all_relevant_course_ids", [])
        
        if not cached_ids:
            # If no context, ask "Which field?"
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                topic="General",
                needs_one_question=True,
                slots={
                    "router_one_question": OneQuestion(
                        question="معنديش سياق كفاية، تحب أعرضلك كورسات في أنهي مجال؟",
                        choices=["Programming", "Data Science", "Marketing", "Business", "Design"]
                    )
                },
                confidence=1.0
            )

        # Calculate new offset
        pagination_offset = session_state.get("pagination_offset", 0)
        new_offset = pagination_offset + 5
        
        # Wrap around if reached the end
        if new_offset >= len(cached_ids):
            new_offset = 0
            
        # Update session state for next call (main.py will persist this)
        session_state["pagination_offset"] = new_offset
        
        # Get next batch
        next_batch_ids = cached_ids[new_offset : new_offset + 5]
        
        # Return as a special COURSE_SEARCH with pre-retrieved IDs
        return IntentResult(
            intent=IntentType.COURSE_SEARCH,
            topic=session_state.get("last_topic", "General"),
            needs_courses=True,
            confidence=1.0,
            slots={
                "pre_retrieved_ids": next_batch_ids,
                "is_pagination": True
            }
        )

    def _resolve_pending(self, pending: dict, msg_lower: str, msg_clean: str, session_state: dict) -> Optional[IntentResult]:
        kind = pending.get("kind")
        yes_words = {"ماشي","تمام","اه","أه","ايوه","أيوة","ok","okay","yes","yep"}

        # (A) Choice Selection
        if kind == "choices":
            choices = pending.get("choices", [])
            norm = [c.strip().lower() for c in choices]
            if msg_lower in norm:
                selected = choices[norm.index(msg_lower)]
                on_select = pending.get("on_select", {})
                
                # Logic to determine topic
                parent = on_select.get("parent_topic")
                topic_mode = on_select.get("topic_mode", "selected")
                topic = selected
                
                if topic_mode == "selected_or_parent" and parent:
                    session_state["last_subtopic"] = selected
                    topic = parent

                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=topic,
                    specific_course=selected,
                    needs_courses=True,
                    confidence=1.0
                )

        # (B) Numeric Selection
        elif kind == "numeric" and msg_clean.isdigit():
            idx = int(msg_clean) - 1
            opts = pending.get("options", [])
            if 0 <= idx < len(opts):
                selected = opts[idx]
                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )

        # (C) Yes/No Confirmation
        elif kind == "yesno" and msg_lower in yes_words:
            yes_action = pending.get("yes_action", "SHOW_COURSES")
            last_topic = session_state.get("last_topic") or pending.get("topic")

            if yes_action == "SHOW_COURSES":
                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=last_topic,
                    needs_courses=True,
                    confidence=1.0
                )
            else:
                return IntentResult(
                    intent=IntentType.CAREER_GUIDANCE,
                    topic=last_topic,
                    needs_explanation=True,
                    confidence=1.0
                )
        
        return None

    def _resolve_one_question(self, last_q: dict, msg_lower: str, msg_clean: str, match_original: str) -> Optional[IntentResult]:
        choices = last_q.get("choices", [])
        choices_norm = [c.strip().lower() for c in choices]

        if msg_lower in choices_norm:
            selected = choices[choices_norm.index(msg_lower)]
            logger.info(f"FollowupResolver: Choice Resolution '{match_original}' -> '{selected}'")
            
            # Deterministic Routing Maps
            marketing_subtracks = {"digital marketing", "social media", "content marketing", "content creation", "performance ads", "brand marketing", "analytics", "seo & sem"}
            data_paths = {"data analysis", "machine learning", "data engineering", "power bi / excel", "big data"}
            sales_paths = {"b2b sales", "cold calling", "closing deals", "sales management", "negotiation"}
            programming_paths = {"web development", "mobile apps", "python & ai", "backend systems", "devops"}
            
            sel_lower = selected.strip().lower()
            
            # Default to Course Search for the specific selection
            # (Simplifies the logic from main.py which had identical blocks)
            return IntentResult(
                intent=IntentType.COURSE_SEARCH,
                topic="Marketing" if sel_lower == "marketing" else selected,
                needs_courses=True,
                confidence=1.0
            )
            
        return None
