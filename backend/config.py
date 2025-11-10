"""Configuration management for the backend API."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


# Fix empty CORS_ORIGINS env var before pydantic_settings tries to parse it as JSON
_cors_origins_env = os.environ.get('CORS_ORIGINS', '').strip()
if not _cors_origins_env:
    os.environ['CORS_ORIGINS'] = "https://galcohensius.github.io,https://galcohensius.github.io/whatsapp-recommendations-extractor,http://localhost:8000"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/whatsapp_recommendations"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # CORS - comma-separated string that gets split into list
    CORS_ORIGINS: str = "https://galcohensius.github.io,https://galcohensius.github.io/whatsapp-recommendations-extractor,http://localhost:8000"
    
    # Security
    SECRET_KEY: str = "change-me-in-production"
    
    # File upload limits
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB in bytes
    
    # Processing timeout (in seconds)
    PROCESSING_TIMEOUT: int = 30 * 60  # 30 minutes
    
    # Retention period (in days)
    RETENTION_DAYS: int = 1
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# Global settings instance
settings = Settings()
