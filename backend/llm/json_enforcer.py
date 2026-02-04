"""
Career Copilot RAG Backend - JSON Enforcer
Enforces strict JSON outputs using Pydantic schemas with one-pass repair.
"""
import json
import logging
import re
from typing import Type, Dict, Any, Union
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

def enforce_json(text: str, schema_model: Type[BaseModel] = None) -> Union[Dict[str, Any], BaseModel]:
    """
    Parses text into JSON, repairs common errors, and validates against a Pydantic schema if provided.
    Returns a dict (if no schema) or the Pydantic instance.
    """
    # 1. Strip Code Fences (```json ... ```)
    clean_text = text.strip()
    if "```" in clean_text:
        # Extract content between first ```json or ``` and the next ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        if match:
            clean_text = match.group(1)
            
    # 2. Extract first JSON object {...}
    # This helps if there is preamble text before the JSON
    brace_match = re.search(r"\{[\s\S]*\}", clean_text)
    if brace_match:
        clean_text = brace_match.group(0)

    # 3. Repair Smart Quotes
    clean_text = clean_text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON Decode Error (Attempting simplistic fix): {e}")
        # Very basic fix: sometimes newlines break string values in valid JSON
        # This is a risky repair, but 'strict=False' in loads sometimes helps.
        # For now, just logging and re-raising or returning error dict depends on policy.
        # Requirement: "If still invalid, return a safe fallback object... plus meta.error"
        # We will let the caller handle the fallback, here we raise.
        raise ValueError(f"Invalid JSON format: {e}")

    # 4. Validate against Schema
    if schema_model:
        try:
            return schema_model.model_validate(data)
        except ValidationError as ve:
            logger.error(f"Schema Validation Failed: {ve}")
            raise ValueError(f"Schema validation failed: {ve}")
            
    return data
