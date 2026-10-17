"""Application configuration loaded strictly from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed settings source (``.env`` / environment)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(..., description="Telegram Bot API token")

    # --- OpenRouter ---
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1", description="OpenRouter API base url"
    )
    openrouter_app_name: str = Field("OpenRouter Telegram Bot")
    openrouter_app_url: str = Field("https://github.com/")

    # --- Transcription (OpenAI compatible endpoint, e.g. OpenAI/Groq) ---
    transcription_base_url: str = Field("https://api.openai.com/v1")
    transcription_api_key: str = Field("")
    transcription_model: str = Field("whisper-1")

    # --- Access ---
    admin_ids_raw: str = Field("", description="Comma separated Telegram user ids")
    daily_request_limit: int = Field(200, description="Per-user daily request cap")
    throttling_rate: float = Field(0.7, description="Seconds between messages")

    # --- Model defaults ---
    default_model: str = Field("nvidia/nemotron-3.5-super-vl:free")
    default_temperature: float = Field(0.7)
    max_history_messages: int = Field(12)
    max_context_tokens: int = Field(6000)
    max_output_tokens: int = Field(2048)

    # --- Storage ---
    database_path: str = Field("bot.db")
    log_level: str = Field("INFO")

    @property
    def admin_ids(self) -> list[int]:
        """Parse ``ADMIN_IDS_RAW`` into a list of integers."""
        ids: list[int] = []
        for chunk in self.admin_ids_raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk:
                try:
                    ids.append(int(chunk))
                except ValueError:
                    continue
        return ids

    @property
    def transcription_key(self) -> str:
        """Fall back to the OpenRouter key if a dedicated key is not provided."""
        return self.transcription_api_key or self.openrouter_api_key


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
