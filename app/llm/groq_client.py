"""
Groq LLM client implementation.

Provides streaming and non-streaming chat completions using Groq's API.
"""
import os
from typing import AsyncGenerator, List, Dict
from groq import AsyncGroq
from app.llm.base import BaseLLM


class GroqLLM(BaseLLM):
    """
    Groq LLM implementation for fast cloud-based inference.
    
    Supports models like llama-3.1-8b-instant, llama-3.1-70b-versatile, etc.
    """
    
    def __init__(
        self, 
        api_key: str = None,
        model: str = None
    ):
        """
        Initialize Groq LLM client.
        
        Args:
            api_key: Groq API key. Defaults to GROQ_API_KEY env var.
            model: Model name. Defaults to GROQ_MODEL env var or llama-3.1-8b-instant.
        
        Raises:
            ValueError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Set it in environment variables or pass to constructor."
            )
        
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.client = AsyncGroq(api_key=self.api_key)
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a non-streaming response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to Groq API
            
        Returns:
            Complete response text
            
        Raises:
            Exception: If the API request fails
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            # Re-raise with more context
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "429" in error_msg:
                raise Exception("Groq rate limit exceeded. Please try again later.")
            elif "authentication" in error_msg or "401" in error_msg:
                raise Exception("Invalid Groq API key. Check your GROQ_API_KEY environment variable.")
            elif "model" in error_msg and "not found" in error_msg:
                raise Exception(f"Model '{self.model}' not found. Check GROQ_MODEL environment variable.")
            else:
                raise Exception(f"Groq API error: {str(e)}")
    
    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to Groq API
            
        Yields:
            Response text chunks as they arrive
            
        Raises:
            Exception: If the API request fails
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                # Extract content from delta
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                        
        except Exception as e:
            # Re-raise with more context
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "429" in error_msg:
                raise Exception("Groq rate limit exceeded. Please try again later.")
            elif "authentication" in error_msg or "401" in error_msg:
                raise Exception("Invalid Groq API key. Check your GROQ_API_KEY environment variable.")
            elif "model" in error_msg and "not found" in error_msg:
                raise Exception(f"Model '{self.model}' not found. Check GROQ_MODEL environment variable.")
            else:
                raise Exception(f"Groq API error: {str(e)}")
