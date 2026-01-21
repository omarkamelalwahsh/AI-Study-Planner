from enum import Enum
from typing import Dict, Any, List

class ConversationState(str, Enum):
    OPEN_CHAT = "OPEN_CHAT"
    GOAL_CLARIFICATION = "GOAL_CLARIFICATION"
    DOMAIN_SELECTION = "DOMAIN_SELECTION"
    COURSE_OFFER = "COURSE_OFFER"
    PLAN_CONFIRMATION = "PLAN_CONFIRMATION"
    PLAN_GENERATION = "PLAN_GENERATION"

class StateMachine:
    @staticmethod
    def get_next_state(current_state: str, user_intent: str, context: Dict[str, Any]) -> str:
        # Simple transition logic
        if current_state == ConversationState.OPEN_CHAT:
            return ConversationState.GOAL_CLARIFICATION
        
        if current_state == ConversationState.GOAL_CLARIFICATION:
            if context.get("goal_specified"):
                return ConversationState.DOMAIN_SELECTION
            return ConversationState.GOAL_CLARIFICATION

        if current_state == ConversationState.DOMAIN_SELECTION:
            if context.get("domain_specified"):
                return ConversationState.COURSE_OFFER
            return ConversationState.DOMAIN_SELECTION

        if current_state == ConversationState.COURSE_OFFER:
            if context.get("course_accepted"):
                return ConversationState.PLAN_CONFIRMATION
            return ConversationState.COURSE_OFFER

        return current_state
