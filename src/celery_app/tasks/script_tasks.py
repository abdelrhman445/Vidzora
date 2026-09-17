from celery import shared_task

from src.config.constants import VideoStatus
from src.database.models.video import Scene
from src.database.repository import VideoRepositorySync
from src.services.ai_service import generate_script, structure_custom_script
from src.utils.file_manager import JobWorkspace
from src.utils.logger import logger


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def generate_script_task(self, video_id: str, reply_to_message_id: int) -> None:
    from src.celery_app.notify import notify_error, notify_script_ready

    job = VideoRepositorySync.get(video_id)
    if job is None:
        logger.error(f"[{video_id}] Job not found for script generation")
        return

    workspace = JobWorkspace(video_id).create()

    try:
        data = generate_script(job.prompt)
        scenes = [Scene(**s) for s in data["scenes"]]

        workspace.script_path().write_text(str(data), encoding="utf-8")

        VideoRepositorySync.update(
            video_id,
            {
                "title": data["title"],
                "scenes": [s.model_dump() for s in scenes],
                "status": VideoStatus.SCRIPT_PENDING_APPROVAL.value,
            },
        )

        preview = "\n".join(f"<b>Scene {s.scene_number}:</b> {s.voiceover_text}" for s in scenes)
        notify_script_ready(job.chat_id, video_id, data["title"], preview)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[{video_id}] Script generation failed")
        VideoRepositorySync.set_status(video_id, VideoStatus.FAILED, str(exc))
        notify_error(job.chat_id, f"Script generation failed: {exc}")


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def structure_custom_script_task(self, video_id: str, reply_to_message_id: int) -> None:
    """
    'Bring your own script' path. The user already approved their own
    words by writing them, so this skips the Script approval gate entirely
    and dispatches straight into audio generation — matching the request
    that a pasted script should 'just speak and continue with the rest of
    the steps'.
    """
    from src.celery_app.notify import notify_error, notify_info
    from src.celery_app.tasks.audio_tasks import generate_audio_task

    job = VideoRepositorySync.get(video_id)
    if job is None:
        logger.error(f"[{video_id}] Job not found for script structuring")
        return

    workspace = JobWorkspace(video_id).create()

    try:
        data = structure_custom_script(job.prompt)
        scenes = [Scene(**s) for s in data["scenes"]]
        workspace.script_path().write_text(str(data), encoding="utf-8")

        VideoRepositorySync.update(
            video_id,
            {
                "title": data["title"],
                "scenes": [s.model_dump() for s in scenes],
                "status": VideoStatus.SCRIPT_APPROVED.value,
            },
        )

        notify_info(
            job.chat_id,
            f"✅ Script split into {len(scenes)} scenes — generating the voiceover now...",
        )
        generate_audio_task.delay(video_id, reply_to_message_id)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[{video_id}] Custom script structuring failed")
        VideoRepositorySync.set_status(video_id, VideoStatus.FAILED, str(exc))
        notify_error(job.chat_id, f"Couldn't process your script: {exc}")
