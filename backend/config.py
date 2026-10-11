"""Application configuration loaded from .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration read from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- AI ---
    GEMINI_API_KEY: str
    GROQ_API_KEY: Optional[str] = None
    CEREBRAS_API_KEY: Optional[str] = None
    AI_PROVIDER: str = "gemini"  # "gemini" | "groq" | "cerebras"

    # --- Resend ---
    RESEND_API_KEY: Optional[str] = None

    # --- Gmail ---
    GMAIL_FROM: str
    SENDER_NAME: str = "Rushil Reddy Chirla"

    # --- Sending behaviour ---
    DAILY_SEND_LIMIT: int = 10
    DRY_RUN: bool = True

    # --- Paths ---
    RESUME_PATH: str = "./resume/resume.pdf"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./cold_email.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
