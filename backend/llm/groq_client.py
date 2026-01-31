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
    
    async def _call_with_retry(self, func, *args, **kwargs):
        """Helper for exponential backoff retry (Requirement G) - Non-blocking."""
        import asyncio
        import random
        from functools import partial
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Run synchronous client call in a thread to avoid blocking (Fixed V16)
                # functools.partial is needed because to_thread takes a func and args
                p_func = partial(func, *args, **kwargs)
                return await asyncio.to_thread(p_func)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Groq final failure after {max_retries} attempts: {e}")
                    raise
                
                # Check for rate limit or transient errors
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(f"Groq attempt {attempt+1} failed ({e}). Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text response from Groq."""
        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self._call_with_retry(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content or ""
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response from Groq."""
        json_system = (system_prompt or "") + "\n\nIMPORTANT: You MUST respond with valid JSON only."
        messages = [
            {"role": "system", "content": json_system},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self._call_with_retry(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error(f"Groq API JSON error: {e}")
            raise

# Factory function
def get_llm_client() -> LLMBase:
    return GroqClient()
