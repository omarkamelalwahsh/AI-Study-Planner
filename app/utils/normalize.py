"""
Text Normalization Utility
Extracts structured information (path/category/level) from user messages
"""

from typing import Dict, Any, Optional


def normalize_text(user_message: str, mapping: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Normalize user input to extract path, category, or level.
    
    Args:
        user_message: Raw user input text
        mapping: LEARNING_MAPPING dictionary
        
    Returns:
        {
            "type": "path" | "category" | "level" | "unknown",
            "value": canonical value or None
        }
    """
    if not user_message:
        return {"type": "unknown", "value": None}
    
    # Normalize input: lowercase and strip
    normalized = user_message.lower().strip()
    
    # Priority 1: Check for PATH matches (most specific)
    for path_key, path_data in mapping.get("paths", {}).items():
        aliases = path_data.get("aliases", [])
        for alias in aliases:
            if alias.lower() in normalized:
                return {
                    "type": "path",
                    "value": path_data["canonical"]
                }
    
    # Priority 2: Check for LEVEL matches
    for level_key, level_data in mapping.get("levels", {}).items():
        aliases = level_data.get("aliases", [])
        for alias in aliases:
            if alias.lower() in normalized:
                return {
                    "type": "level",
                    "value": level_data["canonical"]
                }
    
    # Priority 3: Check for CATEGORY matches (least specific)
    for cat_key, cat_data in mapping.get("categories", {}).items():
        aliases = cat_data.get("aliases", [])
        for alias in aliases:
            if alias.lower() in normalized:
                return {
                    "type": "category",
                    "value": cat_data["canonical"]
                }
    
    # No match found
    return {"type": "unknown", "value": None}


def extract_path_from_message(user_message: str, mapping: Dict[str, Any]) -> Optional[str]:
    """
    Quick helper to extract only path information.
    
    Returns:
        Canonical path name or None
    """
    result = normalize_text(user_message, mapping)
    if result["type"] == "path":
        return result["value"]
    return None


def extract_level_from_message(user_message: str, mapping: Dict[str, Any]) -> Optional[str]:
    """
    Quick helper to extract only level information.
    
    Returns:
        Canonical level (Beginner/Intermediate/Advanced) or None
    """
    result = normalize_text(user_message, mapping)
    if result["type"] == "level":
        return result["value"]
    return None
