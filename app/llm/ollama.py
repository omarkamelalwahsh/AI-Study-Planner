import os
import httpx
import json
from typing import AsyncGenerator, List, Dict, Optional
from app.llm.base import BaseLLM


class OllamaLLM(BaseLLM):
    """
    Ollama LLM implementation for local models (e.g., Mixtral 8x7B).
    
    Supports both streaming and non-streaming chat completions via Ollama's HTTP API.
    """
    
    def __init__(
        self, 
        model: str = None,
        base_url: str = None,
        timeout: int = 120
    ):
        """
        Initialize Ollama LLM client.
        
        Args:
            model: Model name (e.g., "mixtral:8x7b"). Defaults to OLLAMA_MODEL env var.
            base_url: Ollama API base URL. Defaults to OLLAMA_BASE_URL env var or http://localhost:11434
            timeout: Request timeout in seconds
        """
        self.model = model or os.getenv("OLLAMA_MODEL", "mixtral:8x7b")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = timeout
        
        # Validate base_url format
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = f"http://{self.base_url}"
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a non-streaming response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to Ollama API
            
        Returns:
            Complete response text
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        **kwargs
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.ConnectError as e:
                raise ConnectionError(
                    f"Failed to connect to Ollama at {self.base_url}. "
                    f"Is Ollama running? Error: {str(e)}"
                )
            except httpx.HTTPError as e:
                raise RuntimeError(f"Ollama API error: {str(e)}")
    
    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to Ollama API
            
        Yields:
            Response text chunks as they arrive
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        **kwargs
                    }
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                
                                # Extract content from message
                                if "message" in data and "content" in data["message"]:
                                    content = data["message"]["content"]
                                    if content:  # Only yield non-empty content
                                        yield content
                                        
                                # Check if done
                                if data.get("done", False):
                                    break
                                    
                            except json.JSONDecodeError:
                                # Skip malformed JSON lines
                                continue
                                
            except httpx.ConnectError as e:
                raise ConnectionError(
                    f"Failed to connect to Ollama at {self.base_url}. "
                    f"Is Ollama running? Error: {str(e)}"
                )
            except httpx.HTTPError as e:
                raise RuntimeError(f"Ollama API error: {str(e)}")
