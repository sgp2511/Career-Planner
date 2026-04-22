"""
Application configuration via pydantic-settings.

Loads from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration for the Career Relocation Planner API."""

    # --- Application ---
    APP_NAME: str = "Career Relocation Planner API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./relocation_planner.db"

    # --- JWT Authentication ---
    JWT_SECRET_KEY: str = "change-this-to-a-random-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Groq LLM ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- Data Layer ---
    DATA_DIR: str = "app/data"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Using lru_cache ensures the .env file is read only once.
    """
    return Settings()
