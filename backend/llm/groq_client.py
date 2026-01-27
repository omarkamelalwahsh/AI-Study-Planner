"""
Career Copilot RAG Backend - Groq LLM Client
Implementation of LLM interface using Groq API.
"""
import json
import re
import logging
from typing import Optional, Dict, Any

from groq import Groq
from llm.base import LLMBase
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)


class GroqClient(LLMBase):
    """Groq LLM client implementation."""
    
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set in environment")
        
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL
        logger.info(f"Initialized Groq client with model: {self.model}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text response from Groq."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response from Groq."""
        # Add JSON instruction to system prompt
        json_system = (system_prompt or "") + "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no explanation, just the JSON object."
        
        messages = [
            {"role": "system", "content": json_system},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content or "{}"
            
            # Parse JSON
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Try to extract JSON from response
            content = response.choices[0].message.content or ""
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


# Factory function
def get_llm_client() -> LLMBase:
    """Get the configured LLM client."""
    return GroqClient()
