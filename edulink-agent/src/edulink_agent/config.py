"""Configuration objects for the Edulink agent."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration pulled from environment variables."""

    school_code: str | None = Field(
        default=None,
        validation_alias="EDULINK_SCHOOL_CODE",
        description="Optional school/institution identifier used during login.",
    )
    username: str = Field(validation_alias="EDULINK_USERNAME")
    password: SecretStr = Field(validation_alias="EDULINK_PASSWORD")
    base_url: str = Field(default="https://www.edulinkone.com", validation_alias="EDULINK_BASE_URL")
    headless: bool = Field(default=True, validation_alias="EDULINK_HEADLESS")
    timeout_seconds: int = Field(default=30, validation_alias="EDULINK_TIMEOUT_SECONDS")
    timezone: str = Field(default="Europe/London", validation_alias="EDULINK_TIMEZONE")
    child_name: str | None = Field(default=None, validation_alias="EDULINK_CHILD_NAME")

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ServiceInfo(BaseModel):
    """Metadata returned by the API/CLI."""

    generated_at: str
    timezone: str
