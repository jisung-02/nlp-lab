"""Application settings and environment loading."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    app_name: str = "NLP Lab Website"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_domain: str | None = None
    secret_key: str = "change-me"

    database_url: str = "sqlite:///./nlp_lab.db"

    contact_email: str = "lab@example.com"
    contact_address: str = "Seoul, Republic of Korea"
    tls_admin_email: str | None = None
    google_site_verification: str | None = None
    naver_site_verification: str | None = None

    admin_username: str = "admin"
    admin_password: str = "change-me-now"
    admin_session_max_age_seconds: int = Field(default=60 * 60 * 8, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_credentials(self) -> Settings:
        if self.is_production:
            if len(self.secret_key) < 32 or self.secret_key == "change-me":
                raise ValueError("Production SECRET_KEY must contain at least 32 characters")
            if self.admin_password == "change-me-now" or not self.admin_password.strip():
                raise ValueError("Set a non-default ADMIN_PASSWORD in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
