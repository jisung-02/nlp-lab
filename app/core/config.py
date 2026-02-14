"""Application settings and environment loading."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    app_name: str = "NLP Lab Website"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    secret_key: str = "change-me"

    database_url: str = "sqlite:///./nlp_lab.db"

    contact_email: str = "lab@example.com"
    contact_address: str = "Seoul, Republic of Korea"
    contact_map_url: str = "https://maps.google.com"

    admin_username: str = "admin"
    admin_password: str = "change-me-now"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
