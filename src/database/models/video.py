"""
Pydantic schema for a video generation job.
This is the single source of truth for pipeline state — the bot and every
Celery task read/write this document, keyed by `video_id`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.config.constants import MediaType, SourceType, VideoStatus


class Scene(BaseModel):
    scene_number: int
    voiceover_text: str
    image_prompt: str

    # Which kind of visual this scene resolves to. AI decides per-scene when
    # ENABLE_STOCK_FOOTAGE is on (e.g. "video" for action/motion beats,
    # "image" for conceptual/static ones) — both media types coexist in the
    # same final render.
    media_type: MediaType = MediaType.IMAGE

    audio_path: str | None = None
    audio_duration_sec: float | None = None

    image_path: str | None = None   # populated when media_type == IMAGE
    video_path: str | None = None   # populated when media_type == VIDEO (stock footage)


class VideoJob(BaseModel):
    video_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    chat_id: int
    user_id: int

    prompt: str
    source_type: SourceType = SourceType.AI_GENERATED
    status: VideoStatus = VideoStatus.CREATED

    title: str | None = None
    scenes: list[Scene] = Field(default_factory=list)

    final_video_path: str | None = None
    error_message: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> dict[str, Any]:
        data = self.model_dump()
        data["status"] = self.status.value
        data["source_type"] = self.source_type.value
        return data

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> "VideoJob":
        doc = dict(doc)
        doc.pop("_id", None)
        return cls(**doc)
