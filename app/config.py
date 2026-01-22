"""
Configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_env: Literal["dev", "prod", "test"] = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    log_level: str = "INFO"
    
    # Database
    database_url: str
    
    # LLM (Groq)
    llm_provider: str = "groq"
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"
    groq_timeout_seconds: int = 20
    groq_max_retries: int = 2
    
    # Embeddings
    embed_model_name: str = "intfloat/multilingual-e5-small"
    faiss_index_path: str = "data/faiss_index"
    
    # Retrieval
    max_retrieval_results: int = 10
    fuzzy_match_threshold: int = 80  # For fuzzywuzzy
    
    # Feature Flags
    enable_memory: bool = True
    enable_pdf: bool = True
    use_reranker: bool = False
    enable_rate_limiting: bool = False
    
    # Frontend
    vite_api_base_url: str = "http://localhost:8001"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "prod"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "dev"


# Global settings instance
settings = Settings()
