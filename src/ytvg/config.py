from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    telegram_admin_ids: str = ""

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "ytvg"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    pollinations_api_key: str = ""
    pollinations_image_model: str = "nanobanana-2"
    image_fallback_model: str = "qwen-image-3"
    image_timeout_sec: float = 90.0

    tts_voice: str = "en-US-AndrewNeural"
    tts_rate: str = "+0%"

    temp_dir: Path = Path("./temp")
    temp_ttl_hours: int = 24

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    video_bitrate: str = "4M"

    log_level: str = "INFO"
    bot_event_channel: str = "ytvg:bot:events"

    @property
    def admin_ids(self) -> set[int]:
        if not self.telegram_admin_ids.strip():
            return set()
        return {int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
