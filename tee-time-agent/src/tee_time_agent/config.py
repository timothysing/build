"""Configuration objects and helpers for the tee time agent."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables."""

    brs_username: str = Field(..., alias="BRS_USERNAME")
    brs_password: SecretStr = Field(..., alias="BRS_PASSWORD")
    club_slug: str = Field(..., alias="CLUB_SLUG")
    course_id: str = Field("1", alias="COURSE_ID")
    base_url: HttpUrl = Field("https://members.brsgolf.com", alias="BASE_URL")
    login_url: Optional[HttpUrl] = Field(None, alias="LOGIN_URL")
    headless: bool = Field(True, alias="HEADLESS")
    timeout_seconds: int = Field(45, alias="TIMEOUT_SECONDS")
    telegram_bot_token: SecretStr = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., alias="TELEGRAM_CHAT_ID")
    ollama_base_url: HttpUrl = Field("http://ollama.ollama.svc.cluster.local:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field("gemma3:12b", alias="OLLAMA_MODEL")
    environment: str = Field("production", alias="ENVIRONMENT")

    model_config = SettingsConfigDict(
        env_prefix="TEE_AGENT_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
    )

    @field_validator("login_url", mode="before")
    @classmethod
    def default_login_url(cls, value: Optional[str], values: dict[str, object]) -> Optional[str]:
        """Fill in the login URL from the club slug if not provided."""
        if value:
            return value
        base_url = str(values.get("base_url") or "https://members.brsgolf.com").rstrip("/")
        club_slug = values.get("club_slug")
        if not club_slug:
            raise ValueError("club_slug must be provided when login_url is not set")
        return f"{base_url}/{club_slug}/login"

    def tee_sheet_url(self, target_date: date) -> str:
        """Construct the tee sheet URL for a specific date."""
        return (
            f"{str(self.base_url).rstrip('/')}/"
            f"{self.club_slug}/tee-sheet/{self.course_id}/"
            f"{target_date:%Y/%m/%d}"
        )

    @property
    def telegram_api_endpoint(self) -> str:
        """Base Telegram Bot API endpoint."""
        return f"https://api.telegram.org/bot{self.telegram_bot_token.get_secret_value()}"
