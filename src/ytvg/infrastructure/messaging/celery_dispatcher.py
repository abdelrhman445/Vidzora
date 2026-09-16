from __future__ import annotations

from ytvg.workers import tasks as worker_tasks


class CeleryTaskDispatcher:
    """Thin adapter so application code never imports Celery task objects directly."""

    def enqueue_script(self, job_id: str) -> None:
        worker_tasks.generate_script.delay(job_id)

    def enqueue_audio(self, job_id: str) -> None:
        worker_tasks.generate_audio.delay(job_id)

    def enqueue_images(self, job_id: str) -> None:
        worker_tasks.generate_images.delay(job_id)

    def enqueue_video(self, job_id: str) -> None:
        worker_tasks.assemble_video.delay(job_id)

    def enqueue_cleanup(self, job_id: str) -> None:
        worker_tasks.cleanup_job.delay(job_id)
