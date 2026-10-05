from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    admin_api_token: SecretStr = SecretStr("")
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")
    finance_email: str = ""
    finance_password: SecretStr = SecretStr("")

    app_name: str = "ShetiSevek AI"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    demo_user_growth_enabled: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: SecretStr
    meta_verify_token: SecretStr
    meta_app_secret: SecretStr
    meta_access_token: SecretStr
    meta_phone_number_id: str = Field(pattern=r"^\d+$")
    meta_whatsapp_business_account_id: str = Field(pattern=r"^\d+$")
    meta_graph_api_version: str = Field(pattern=r"^v\d+\.\d+$")
    gemini_api_key: SecretStr
    gemini_model: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")
    conversation_history_limit: int = Field(default=20, ge=2, le=200)
    conversation_history_char_limit: int = Field(default=24000, ge=1000, le=200000)
    http_timeout_seconds: float = Field(default=30, ge=1, le=120)
    job_poll_interval_seconds: float = Field(default=2, ge=0.1, le=60)
    job_max_attempts: int = Field(default=5, ge=1, le=20)
    job_stale_seconds: int = Field(default=180, ge=30, le=3600)
    webhook_max_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator(
        "database_url",
        "meta_verify_token",
        "meta_app_secret",
        "meta_access_token",
        "gemini_api_key",
    )
    @classmethod
    def required_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Required secret cannot be blank")
        return value

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value

    @model_validator(mode="after")
    def production_rules(self) -> "Settings":
        if self.app_env == "production" and self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.job_stale_seconds <= self.http_timeout_seconds * 2:
            raise ValueError("JOB_STALE_SECONDS must exceed twice HTTP_TIMEOUT_SECONDS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
