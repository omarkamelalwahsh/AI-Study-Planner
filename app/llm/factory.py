import os
from app.llm.base import BaseLLM
from app.llm.groq_client import GroqLLM

def get_llm() -> BaseLLM:
    """
    Factory function to get the configured LLM provider.
    
    Returns:
        BaseLLM: Configured LLM instance
        
    Raises:
        ValueError: If unsupported LLM provider is specified or required config is missing
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is required. "
                "Get your API key from https://console.groq.com"
            )
        
        return GroqLLM(
            api_key=api_key,
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
