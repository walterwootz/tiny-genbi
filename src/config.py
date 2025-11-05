"""
Configuration management for the GenBI system.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 5556
    
    # LLM Provider Settings
    llm_provider: str = "openai"  # openai, anthropic, local, etc.
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None  # For local LLMs (e.g., http://localhost:11434/v1)
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    
    # Embedding Settings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None  # For local embeddings
    
    # Vector Store Settings
    vector_store_path: str = "./data/vector_store"
    
    # System Settings
    debug: bool = False
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
