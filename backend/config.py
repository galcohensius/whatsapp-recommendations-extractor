"""Configuration management for the backend API."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost/whatsapp_recommendations"
    )
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # CORS
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS",
        "https://galcohensius.github.io,http://localhost:8000"
    ).split(",")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    
    # File upload limits
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB in bytes
    
    # Processing timeout (in seconds)
    PROCESSING_TIMEOUT: int = 30 * 60  # 30 minutes
    
    # Retention period (in days)
    RETENTION_DAYS: int = 1
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

