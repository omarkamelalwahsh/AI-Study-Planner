"""
Career Copilot RAG Backend - Track Resolver (V16 Data-Driven)
Resolves user intent/role to valid "Tracks" (sets of categories) verified against the actual data.
"""
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from data_loader import data_loader
from models import IntentResult, SemanticResult

logger = logging.getLogger(__name__)

class TrackDecision(BaseModel):
    """Result of track resolution."""
    track_name: str
    allowed_categories: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""

class TrackResolver:
    """
    Resolves higher-level Domains/Tracks (e.g. 'Frontend', 'HR') into 
    concrete lists of Categories available in courses.csv (e.g. 'Web Development', 'Human Resources').
    """
    
    def __init__(self):
        # We rely on DataLoader's policies but filter them dynamically
        pass

    def resolve_track(
        self, 
        message: str, 
        semantic_result: Optional[SemanticResult], 
        intent_result: IntentResult
    ) -> TrackDecision:
        """
        Determines the correct Track/Domain and returns VALID categories.
        """
        # 1. Gather signals
        role = intent_result.role
        primary_domain = getattr(intent_result, 'primary_domain', None) or (semantic_result.primary_domain if semantic_result else None)
        message_lower = message.lower()

        # 2. Determine Candidate Track Logic
        # Priority 1: Role (if whitelisted)
        candidate_cats = []
        track_name = "General"
        reason = "Default fallback"
        confidence = 0.0

        all_real_categories = set(c.lower() for c in data_loader.get_all_categories())
        
        # --- LOGIC A: Role Policy ---
        if role:
            role_cats = data_loader.get_categories_for_role(role)
            if role_cats:
                candidate_cats = role_cats
                track_name = role
                reason = f"Matched logic for role: {role}"
                confidence = 0.95
        
        # --- LOGIC B: Primary Domain ---
        if not candidate_cats and primary_domain:
            domain_cats = data_loader.get_categories_for_role(primary_domain)
            if domain_cats:
                candidate_cats = domain_cats
                track_name = primary_domain
                reason = f"Matched logic for domain: {primary_domain}"
                confidence = 0.85

        # --- LOGIC C: Umbrella Topics (Fuzzy) ---
        if not candidate_cats:
            # Check umbrella topics
            umbrella_cats = data_loader.get_umbrella_categories(message)
            if umbrella_cats:
                candidate_cats = umbrella_cats
                track_name = "Umbrella Topic"
                reason = "Matched broad umbrella topic"
                confidence = 0.8

        # --- LOGIC D: Direct Category Match (High Confidence) ---
        if not candidate_cats:
            # Check if user mentioned an exact category
            user_real_cats = []
            for cat in data_loader.get_all_categories(): # Using the sorted list from data_loader
                if cat.lower() in message_lower:
                    user_real_cats.append(cat)
            
            if user_real_cats:
                candidate_cats = user_real_cats
                track_name = "Direct Category"
                reason = f"User mentioned categories: {user_real_cats}"
                confidence = 1.0

        # 3. DATA-DRIVEN FILTERING (CRITICAL) - V17 Uses normalize_category
        # Only allow categories that ACTUALLY exist in the CSV right now.
        norm_to_display = data_loader.get_normalized_categories()  # {normalized: original}
        final_categories = []
        for cat in candidate_cats:
            cat_norm = data_loader.normalize_category(cat)
            if cat_norm in norm_to_display:
                final_categories.append(norm_to_display[cat_norm])
            else:
                logger.warning(f"TrackResolver: Dropping category '{cat}' for track '{track_name}' - NOT found in data.")

        # If we filtered everything away, fallback to empty (General)
        if not final_categories and candidate_cats:
             logger.warning(f"TrackResolver: All categories for '{track_name}' were invalid/missing in data.")
             track_name = "General"
             confidence = 0.0
        
        if not final_categories:
            # Fallback for General Browsing
            track_name = "General"
            reason = "No specific track detected"
            confidence = 0.1

        return TrackDecision(
            track_name=track_name,
            allowed_categories=sorted(list(set(final_categories))), # Dedupe and sort
            confidence=confidence,
            reason=reason
        )

track_resolver = TrackResolver()
