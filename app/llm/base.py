from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any

class BaseLLM(ABC):
    """Abstract Base Class for LLM implementations."""

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a complete response from the LLM.
        
        Args:
            messages: List of message dictionaries (role, content).
            **kwargs: Additional arguments.
            
        Returns:
            The generated text response.
        """
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream response token by token.
        
        Args:
            messages: List of message dictionaries (role, content).
            **kwargs: Additional arguments.
            
        Yields:
            Chunks of generated text.
        """
        pass
