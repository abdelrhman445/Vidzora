"""
Centralized, validated application settings.
Loaded once from environment variables (.env) using pydantic-settings.
Never hardcode secrets anywhere else in the codebase — always import `settings`.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    BOT_TOKEN: str = Field(..., description="Telegram Bot API token from @BotFather")
    ADMIN_USER_IDS: str = Field(default="", description="Comma-separated Telegram user IDs allowed to use the bot")

    # --- MongoDB ---
    MONGO_URI: str = Field(default="mongodb://localhost:27017")
    MONGO_DB_NAME: str = Field(default="youtube_automation")

    # --- Redis / Celery ---
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # --- AI Providers ---
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")

    IMAGE_PROVIDER: str = Field(default="huggingface", description="'huggingface' or 'leonardo'")
    HUGGINGFACE_API_KEY: str = Field(default="")
    HUGGINGFACE_IMAGE_MODEL: str = Field(default="stabilityai/stable-diffusion-xl-base-1.0")
    LEONARDO_API_KEY: str = Field(default="")
    LEONARDO_MODEL_ID: str = Field(default="")

    # --- TTS ---
    TTS_VOICE: str = Field(default="en-US-GuyNeural")

    # --- Video ---
    VIDEO_WIDTH: int = Field(default=1080)
    VIDEO_HEIGHT: int = Field(default=1920)  # vertical (Shorts) by default
    VIDEO_FPS: int = Field(default=30)
    CROSSFADE_DURATION_SEC: float = Field(default=0.6)

    # --- Mixed media (stock video B-roll alongside AI images) ---
    ENABLE_STOCK_FOOTAGE: bool = Field(default=False, description="Let Gemini mix in real video clips per scene")
    PEXELS_API_KEY: str = Field(default="")

    # --- Burned-in captions ---
    ENABLE_SUBTITLES: bool = Field(default=True)
    SUBTITLE_FONT_SIZE: int = Field(default=64)
    SUBTITLE_FONT_PATH: str = Field(default="", description="Path to a .ttf/.otf font; empty = library default")

    # --- Background music ---
    BACKGROUND_MUSIC_PATH: str = Field(
        default="", description="Path to a royalty-free .mp3 under assets/music/ — leave empty to disable"
    )
    BACKGROUND_MUSIC_VOLUME: float = Field(default=0.12, description="0.0-1.0, mixed under the voiceover")

    # --- Intro / outro cards ---
    ENABLE_INTRO_CARD: bool = Field(default=True)
    ENABLE_OUTRO_CARD: bool = Field(default=True)
    OUTRO_TEXT: str = Field(default="Thanks for watching!\nLike & Subscribe")
    INTRO_OUTRO_DURATION_SEC: float = Field(default=2.5)

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    TEMP_DIR: Path = BASE_DIR / "temp"
    ASSETS_DIR: Path = BASE_DIR / "assets"

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.ADMIN_USER_IDS.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
