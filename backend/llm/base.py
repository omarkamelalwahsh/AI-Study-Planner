"""
Career Copilot RAG Backend - LLM Base Interface
Abstract base class for LLM providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class LLMBase(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response from the LLM."""
        pass
