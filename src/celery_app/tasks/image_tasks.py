"""
Visual-asset generation stage. Despite the filename (kept for continuity
with PipelineStage.IMAGES), this now produces the right asset per scene:
  - MediaType.VIDEO -> a Pexels stock clip matching the image_prompt
  - MediaType.IMAGE -> an AI-generated still (Hugging Face/Leonardo)
Stock footage lookup is best-effort: if no suitable clip is found, the
scene silently falls back to an AI image so the pipeline never stalls on
stock-library gaps.
"""
from celery import shared_task

from src.config.constants import MediaType, VideoStatus
from src.database.repository import VideoRepositorySync
from src.services.image_service import generate_image
from src.services.stock_footage_service import fetch_stock_clip
from src.utils.file_manager import JobWorkspace
from src.utils.logger import logger


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def generate_images_task(self, video_id: str, reply_to_message_id: int) -> None:
    from src.celery_app.notify import notify_error, notify_visuals_ready

    job = VideoRepositorySync.get(video_id)
    if job is None:
        logger.error(f"[{video_id}] Job not found for visual generation")
        return

    workspace = JobWorkspace(video_id)
    VideoRepositorySync.set_status(video_id, VideoStatus.IMAGES_GENERATING)

    try:
        media_items: list[tuple[str, str]] = []  # (path, "image"|"video") in scene order
        updated_scenes = []

        for scene in job.scenes:
            if scene.media_type == MediaType.VIDEO:
                video_out = workspace.video_dir_path(scene.scene_number)
                min_duration = scene.audio_duration_sec or 4.0
                found = fetch_stock_clip(scene.image_prompt, video_out, min_duration)

                if found:
                    scene.video_path = str(video_out)
                    media_items.append((str(video_out), "video"))
                    updated_scenes.append(scene.model_dump())
                    continue

                logger.info(f"[{video_id}] No stock clip for scene {scene.scene_number}, falling back to image")
                scene.media_type = MediaType.IMAGE  # fall back in-place

            image_out = workspace.image_path(scene.scene_number)
            generate_image(scene.image_prompt, image_out)
            scene.image_path = str(image_out)
            media_items.append((str(image_out), "image"))
            updated_scenes.append(scene.model_dump())

        VideoRepositorySync.update(
            video_id,
            {"scenes": updated_scenes, "status": VideoStatus.IMAGES_PENDING_APPROVAL.value},
        )
        notify_visuals_ready(job.chat_id, video_id, media_items)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[{video_id}] Visual generation failed")
        VideoRepositorySync.set_status(video_id, VideoStatus.FAILED, str(exc))
        notify_error(job.chat_id, f"Visual generation failed: {exc}")
