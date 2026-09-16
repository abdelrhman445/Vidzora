from __future__ import annotations

from ytvg.domain.entities import VideoJob
from ytvg.domain.enums import JobStatus


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._items: dict[str, VideoJob] = {}

    async def create(self, job: VideoJob) -> VideoJob:
        self._items[job.id] = job.model_copy(deep=True)
        return job

    async def get(self, job_id: str) -> VideoJob | None:
        job = self._items.get(job_id)
        return job.model_copy(deep=True) if job else None

    async def save(self, job: VideoJob) -> VideoJob:
        self._items[job.id] = job.model_copy(deep=True)
        return job

    async def find_active_for_user(self, user_id: int) -> VideoJob | None:
        active = {
            JobStatus.PENDING,
            JobStatus.PROCESSING,
            JobStatus.AWAITING_APPROVAL,
        }
        for job in self._items.values():
            if job.user_id == user_id and job.status in active:
                return job.model_copy(deep=True)
        return None

    async def list_by_status(self, status: JobStatus, limit: int = 50) -> list[VideoJob]:
        return [j.model_copy(deep=True) for j in self._items.values() if j.status == status][:limit]


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def enqueue_script(self, job_id: str) -> None:
        self.calls.append(("script", job_id))

    def enqueue_audio(self, job_id: str) -> None:
        self.calls.append(("audio", job_id))

    def enqueue_images(self, job_id: str) -> None:
        self.calls.append(("images", job_id))

    def enqueue_video(self, job_id: str) -> None:
        self.calls.append(("video", job_id))

    def enqueue_cleanup(self, job_id: str) -> None:
        self.calls.append(("cleanup", job_id))
