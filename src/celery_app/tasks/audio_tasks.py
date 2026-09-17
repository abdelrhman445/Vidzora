from celery import shared_task

from src.config.constants import VideoStatus
from src.database.repository import VideoRepositorySync
from src.services.tts_service import generate_speech
from src.utils.file_manager import JobWorkspace
from src.utils.logger import logger


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def generate_audio_task(self, video_id: str, reply_to_message_id: int) -> None:
    from src.celery_app.notify import notify_audio_ready, notify_error

    job = VideoRepositorySync.get(video_id)
    if job is None:
        logger.error(f"[{video_id}] Job not found for audio generation")
        return

    workspace = JobWorkspace(video_id)
    VideoRepositorySync.set_status(video_id, VideoStatus.AUDIO_GENERATING)

    try:
        audio_paths = []
        updated_scenes = []
        for scene in job.scenes:
            out_path = workspace.audio_path(scene.scene_number)
            duration = generate_speech(scene.voiceover_text, out_path)

            scene.audio_path = str(out_path)
            scene.audio_duration_sec = duration
            updated_scenes.append(scene.model_dump())
            audio_paths.append(out_path)

        VideoRepositorySync.update(
            video_id,
            {"scenes": updated_scenes, "status": VideoStatus.AUDIO_PENDING_APPROVAL.value},
        )
        notify_audio_ready(job.chat_id, video_id, audio_paths)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[{video_id}] Audio generation failed")
        VideoRepositorySync.set_status(video_id, VideoStatus.FAILED, str(exc))
        notify_error(job.chat_id, f"Audio generation failed: {exc}")
