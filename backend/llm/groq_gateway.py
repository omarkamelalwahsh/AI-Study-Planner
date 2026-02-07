"""
Career Copilot RAG Backend - Groq Gateway
Single entry point for all Groq LLM interaction with robustness layers.
"""
import logging
import time
import asyncio
from typing import Optional, Dict, Any, Type
import uuid

from groq import Groq
from pydantic import BaseModel

from config import GROQ_API_KEY, GROQ_MODEL
from llm.base import LLMBase
from llm.json_enforcer import enforce_json

logger = logging.getLogger(__name__)

class GroqGateway(LLMBase):
    """
    Central Gateway to Groq API.
    Enforces:
    - Retries (Exponential Backoff)
    - JSON Schema Validation
    - Latency Logging
    """
    
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set in environment")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL
        # Configurable settings
        self.max_retries = 2
        self.base_delay = 1.0 # seconds
        self.timeout = 30.0 # seconds
        
        logger.info(f"Initialized GroqGateway [Model: {self.model}]")

    async def _call_api_with_retry(self, messages: list, **kwargs) -> Any:
        """Execute Groq API call with exponential backoff (max 6s total backoff)."""
        import random
        from functools import partial
        
        last_exception = None
        total_backoff = 0.0
        MAX_TOTAL_BACKOFF = 6.0  # FIX 6: Cap total retry sleep time
        
        for attempt in range(self.max_retries + 1):
            try:
                # synchronous call in thread for non-blocking IO
                p_func = partial(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    timeout=self.timeout,
                    **kwargs
                )
                start_ts = time.time()
                response = await asyncio.to_thread(p_func)
                latency = (time.time() - start_ts) * 1000
                
                # Log usage if available
                usage = response.usage
                p_tokens = usage.prompt_tokens if usage else 0
                c_tokens = usage.completion_tokens if usage else 0
                
                # If request_id was passed in kwargs (it's not valid for create(), but we track it separately)
                # We can't pass it to create(), so we rely on the caller to log the start.
                # Here we log success.
                logger.info(f"Groq Success | Latency: {latency:.2f}ms | In: {p_tokens} / Out: {c_tokens}")
                
                return response
                
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # FIX 6: Fail fast on rate limit if already over budget
                is_rate_limit = "429" in error_str or "rate limit" in error_str
                
                if attempt < self.max_retries and total_backoff < MAX_TOTAL_BACKOFF:
                    delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 0.5), MAX_TOTAL_BACKOFF - total_backoff)
                    total_backoff += delay
                    logger.warning(f"Groq Error (Attempt {attempt+1}/{self.max_retries}): {e}. Retrying in {delay:.2f}s... (Total: {total_backoff:.2f}s)")
                    await asyncio.sleep(delay)
                else:
                    if is_rate_limit:
                        logger.error(f"Groq Rate Limited (429). Failing fast after {total_backoff:.2f}s backoff.")
                    else:
                        logger.error(f"Groq Fatal Error after {self.max_retries+1} attempts: {e}")
                    break
                    
        raise last_exception

    async def chat_json(
        self, 
        prompt: str, 
        schema_model: Type[BaseModel] = None, 
        system_prompt: Optional[str] = None,
        request_id: Optional[str] = None,
        temperature: float = 0.3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request and return strictly validated JSON.
        """
        rid = request_id or str(uuid.uuid4())
        
        # Prepare messages
        sys_p = system_prompt or "You are a helpful assistant."
        # Force JSON instruction
        sys_p += "\n\nIMPORTANT: You MUST respond with valid JSON only."
        
        messages = [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self._call_api_with_retry(
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                **kwargs
            )
            
            raw_content = response.choices[0].message.content or "{}"
            
            # Enforce Schema
            try:
                validated_data = enforce_json(raw_content, schema_model)
                # If it's a model instance, convert to dict
                if isinstance(validated_data, BaseModel):
                    return validated_data.dict()
                return validated_data
                
            except ValueError as ve:
                logger.error(f"[{rid}] JSON Enforcement Failed: {ve}")
                # Return 'safe' error dict with meta if possible, OR
                # Since we are the gateway, we might just raise and let the handler wrap it.
                # Requirement: "return a safe fallback object... plus meta.error"
                # If we raise, the caller catches it.
                # But let's follow the instruction: "Return a safe fallback object".
                # We don't know the schema's safe fallback here easily without defaults.
                # BETTER APPROACH: Raise, and let response_builder handle the fallback logic.
                raise
                
        except Exception as e:
            logger.error(f"[{rid}] GroqGateway.chat_json Failed: {e}")
            raise

    # Legacy method support for drop-in replacement
    async def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=1024) -> str:
        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        resp = await self._call_api_with_retry(messages, temperature=temperature, max_tokens=max_tokens)
        return resp.choices[0].message.content or ""
        
    async def generate_json(self, prompt, system_prompt=None, temperature=0.3, **kwargs) -> Dict[str, Any]:
        # Legacy adaptor pointing to chat_json (no schema)
        return await self.chat_json(prompt, system_prompt=system_prompt, temperature=temperature, **kwargs)

# Singleton Pattern for Gateway
_gateway_instance = None

def get_llm_gateway() -> GroqGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = GroqGateway()
    return _gateway_instance

# factory for legacy compatibility
def get_llm_client() -> LLMBase:
    return get_llm_gateway()
