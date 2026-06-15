from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Green Oracle 2026"
    app_env: str = "development"
    app_base_url: str = "http://127.0.0.1:8000"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_translation_model: str = ""
    anthropic_base_url: str = ""
    anthropic_auth_token: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    claude_code_disable_nonessential_traffic: bool = False
    claude_code_attribution_header: str = "0"
    request_timeout_s: int = Field(default=20, ge=5, le=120)
    rate_limit_per_minute: int = Field(default=10, ge=1, le=120)
    demo_fallback_enabled: bool = True
    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_api_key: str = ""
    football_data_competition_code: str = "WC"
    schedule_cache_path: str = "var/schedule_cache.json"
    render_service_name: str = ""
    internal_sync_token: str = "change-me"
    render_disk_mount_path: str = "/var/data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_model_settings(self) -> "Settings":
        has_key = bool(self.openai_api_key.strip())
        has_anthropic = bool(self.anthropic_auth_token.strip() and self.anthropic_base_url.strip())
        if has_key and not self.openai_model.strip():
            raise ValueError("OPENAI_MODEL is required when OPENAI_API_KEY is set.")
        if has_key and not self.openai_base_url.strip():
            raise ValueError("OPENAI_BASE_URL is required when OPENAI_API_KEY is set.")
        if self.openai_translation_model.strip() and not (has_key or has_anthropic):
            raise ValueError(
                "OPENAI_TRANSLATION_MODEL requires a configured text-generation provider."
            )
        return self

    @property
    def live_mode_enabled(self) -> bool:
        openai_ready = bool(self.openai_api_key.strip() and self.openai_model.strip() and self.openai_base_url.strip())
        anthropic_ready = bool(self.anthropic_auth_token.strip() and self.anthropic_model.strip() and self.anthropic_base_url.strip())
        return openai_ready or anthropic_ready

    @property
    def translation_model(self) -> str:
        if self.openai_translation_model.strip():
            return self.openai_translation_model
        if self.openai_api_key.strip():
            return self.openai_model
        return self.anthropic_model

    @property
    def schedule_cache_file(self) -> Path:
        configured = Path(self.schedule_cache_path)
        if configured.is_absolute():
            return configured
        disk_root = Path(self.render_disk_mount_path)
        if self.app_env == "production":
            return disk_root / configured
        return Path(configured)


@lru_cache
def get_settings() -> Settings:
    return Settings()
