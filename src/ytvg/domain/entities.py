from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ytvg.domain.enums import JobStatus, Stage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Scene(BaseModel):
    index: int
    voiceover: str
    image_prompt: str
    duration_hint_sec: float = 8.0
    audio_path: str | None = None
    image_path: str | None = None
    duration_sec: float | None = None


class Script(BaseModel):
    title: str
    description: str = ""
    scenes: list[Scene] = Field(default_factory=list)


class VideoJob(BaseModel):
    """Aggregate root tracking a single video through approval gateways."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    chat_id: int
    user_id: int
    prompt: str
    stage: Stage = Stage.INIT
    status: JobStatus = JobStatus.PENDING
    script: Script | None = None
    combined_audio_path: str | None = None
    video_path: str | None = None
    error: str | None = None
    workspace_dir: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def mark_processing(self, stage: Stage) -> None:
        self.stage = stage
        self.status = JobStatus.PROCESSING
        self.error = None
        self.updated_at = utcnow()

    def mark_awaiting(self, stage: Stage) -> None:
        self.stage = stage
        self.status = JobStatus.AWAITING_APPROVAL
        self.updated_at = utcnow()

    def mark_failed(self, message: str) -> None:
        self.status = JobStatus.FAILED
        self.error = message
        self.updated_at = utcnow()

    def mark_cancelled(self) -> None:
        self.status = JobStatus.CANCELLED
        self.updated_at = utcnow()

    def mark_completed(self) -> None:
        self.stage = Stage.DONE
        self.status = JobStatus.COMPLETED
        self.updated_at = utcnow()
