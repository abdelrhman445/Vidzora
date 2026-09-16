from __future__ import annotations

from typing import Protocol

from ytvg.domain.entities import Script, VideoJob
from ytvg.domain.enums import BotEventType, JobStatus, Stage


class JobRepository(Protocol):
    async def create(self, job: VideoJob) -> VideoJob: ...

    async def get(self, job_id: str) -> VideoJob | None: ...

    async def save(self, job: VideoJob) -> VideoJob: ...

    async def find_active_for_user(self, user_id: int) -> VideoJob | None: ...

    async def list_by_status(self, status: JobStatus, limit: int = 50) -> list[VideoJob]: ...


class ScriptGenerator(Protocol):
    async def generate(self, prompt: str) -> Script: ...


class SpeechSynthesizer(Protocol):
    async def synthesize_scene(
        self, *, text: str, output_path: str, voice: str | None = None
    ) -> float:
        """Render TTS to `output_path`. Returns duration in seconds."""


class ImageGenerator(Protocol):
    async def generate(self, *, prompt: str, output_path: str) -> str: ...


class VideoRenderer(Protocol):
    async def assemble(
        self,
        *,
        job: VideoJob,
        image_paths: list[str],
        audio_paths: list[str],
        output_path: str,
    ) -> str: ...


class EventBus(Protocol):
    async def publish(
        self,
        *,
        event_type: BotEventType,
        job_id: str,
        chat_id: int,
        payload: dict | None = None,
    ) -> None: ...


class TaskDispatcher(Protocol):
    """Port used by the bot to enqueue worker jobs (implemented by Celery)."""

    def enqueue_script(self, job_id: str) -> None: ...

    def enqueue_audio(self, job_id: str) -> None: ...

    def enqueue_images(self, job_id: str) -> None: ...

    def enqueue_video(self, job_id: str) -> None: ...

    def enqueue_cleanup(self, job_id: str) -> None: ...


class WorkspaceManager(Protocol):
    def prepare(self, job_id: str) -> str: ...

    def audio_path(self, job_id: str, scene_index: int) -> str: ...

    def image_path(self, job_id: str, scene_index: int) -> str: ...

    def combined_audio_path(self, job_id: str) -> str: ...

    def video_path(self, job_id: str) -> str: ...

    def wipe(self, job_id: str) -> None: ...

    def wipe_all_stale(self) -> int: ...
