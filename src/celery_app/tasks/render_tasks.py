from celery import shared_task

from src.config.constants import VideoStatus
from src.database.repository import VideoRepositorySync
from src.services.render_service import render_video
from src.utils.file_manager import JobWorkspace
from src.utils.logger import logger


@shared_task(bind=True, max_retries=1, default_retry_delay=15)
def render_video_task(self, video_id: str, reply_to_message_id: int) -> None:
    from src.celery_app.notify import notify_error, notify_video_ready

    job = VideoRepositorySync.get(video_id)
    if job is None:
        logger.error(f"[{video_id}] Job not found for rendering")
        return

    workspace = JobWorkspace(video_id)
    VideoRepositorySync.set_status(video_id, VideoStatus.RENDERING)

    try:
        output_path = render_video(job.scenes, workspace.output_path(), title=job.title or job.prompt)
        VideoRepositorySync.update(
            video_id,
            {"final_video_path": str(output_path), "status": VideoStatus.COMPLETED.value},
        )
        notify_video_ready(job.chat_id, output_path, job.title or job.prompt)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[{video_id}] Rendering failed")
        VideoRepositorySync.set_status(video_id, VideoStatus.FAILED, str(exc))
        notify_error(job.chat_id, f"Video rendering failed: {exc}")
        return

    finally:
        # Cleanup runs on success AND failure — never leave temp files behind.
        workspace.cleanup()
