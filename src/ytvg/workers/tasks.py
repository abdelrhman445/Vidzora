from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from ytvg.celery_app import celery_app
from ytvg.config import get_settings
from ytvg.domain.enums import BotEventType, JobStatus, Stage
from ytvg.domain.exceptions import ExternalServiceError
from ytvg.infrastructure.ai.gemini_script import GeminiScriptGenerator
from ytvg.infrastructure.ai.image_pollinations import PollinationsImageGenerator
from ytvg.infrastructure.ai.tts_edge import EdgeTTSSynthesizer
from ytvg.infrastructure.db.mongo import Mongo
from ytvg.infrastructure.db.repositories import MongoJobRepository
from ytvg.infrastructure.media.renderer import FFmpegVideoRenderer
from ytvg.infrastructure.messaging.sync_publisher import publish_bot_event
from ytvg.infrastructure.storage.temp_manager import TempWorkspaceManager

logger = logging.getLogger(__name__)


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run async infrastructure from a sync Celery worker process."""
    return asyncio.run(coro)


async def _with_jobs(fn: Callable[[MongoJobRepository], Any]) -> Any:
    mongo = Mongo(get_settings())
    await mongo.connect()
    try:
        return await fn(MongoJobRepository(mongo.db))
    finally:
        await mongo.close()


def _fail_or_retry(task, job_id: str, exc: Exception, countdown: int):
    max_retries = task.max_retries or 0
    if task.request.retries >= max_retries:
        _run(_fail_job(job_id, str(exc)))
        raise exc
    raise task.retry(exc=exc, countdown=countdown)


@celery_app.task(bind=True, name="ytvg.workers.tasks.generate_script", max_retries=2)
def generate_script(self, job_id: str) -> str:
    try:
        return _run(_generate_script(job_id))
    except Exception as exc:
        logger.exception("generate_script failed for %s", job_id)
        _fail_or_retry(self, job_id, exc, countdown=10)


@celery_app.task(bind=True, name="ytvg.workers.tasks.generate_audio", max_retries=2)
def generate_audio(self, job_id: str) -> str:
    try:
        return _run(_generate_audio(job_id))
    except Exception as exc:
        logger.exception("generate_audio failed for %s", job_id)
        _fail_or_retry(self, job_id, exc, countdown=15)


@celery_app.task(bind=True, name="ytvg.workers.tasks.generate_images", max_retries=1)
def generate_images(self, job_id: str) -> str:
    try:
        return _run(_generate_images(job_id))
    except Exception as exc:
        logger.exception("generate_images failed for %s", job_id)
        _fail_or_retry(self, job_id, exc, countdown=20)


@celery_app.task(bind=True, name="ytvg.workers.tasks.assemble_video", max_retries=1)
def assemble_video(self, job_id: str) -> str:
    try:
        return _run(_assemble_video(job_id))
    except Exception as exc:
        logger.exception("assemble_video failed for %s", job_id)
        _fail_or_retry(self, job_id, exc, countdown=20)


@celery_app.task(name="ytvg.workers.tasks.cleanup_job")
def cleanup_job(job_id: str) -> str:
    workspace = TempWorkspaceManager(get_settings())
    workspace.wipe(job_id)
    return job_id


@celery_app.task(name="ytvg.workers.tasks.sweep_stale_workspaces")
def sweep_stale_workspaces() -> int:
    return TempWorkspaceManager(get_settings()).wipe_all_stale()


async def _generate_script(job_id: str) -> str:
    async def _inner(jobs: MongoJobRepository) -> str:
        job = await jobs.get(job_id)
        if not job:
            return job_id
        job.mark_processing(Stage.SCRIPT)
        await jobs.save(job)

        script = await GeminiScriptGenerator().generate(job.prompt)
        job.script = script
        job.mark_awaiting(Stage.SCRIPT)
        await jobs.save(job)

        publish_bot_event(
            event_type=BotEventType.SCRIPT_READY,
            job_id=job.id,
            chat_id=job.chat_id,
            payload={
                "title": script.title,
                "description": script.description,
                "scenes": [s.model_dump() for s in script.scenes],
            },
        )
        return job.id

    return await _with_jobs(_inner)


async def _generate_audio(job_id: str) -> str:
    workspace = TempWorkspaceManager()
    tts = EdgeTTSSynthesizer()

    async def _inner(jobs: MongoJobRepository) -> str:
        job = await jobs.get(job_id)
        if not job or not job.script:
            raise ExternalServiceError("Job has no script to narrate")
        job.mark_processing(Stage.AUDIO)
        await jobs.save(job)
        workspace.prepare(job.id)

        audio_files: list[str] = []
        for scene in job.script.scenes:
            path = workspace.audio_path(job.id, scene.index)
            duration = await tts.synthesize_scene(text=scene.voiceover, output_path=path)
            scene.audio_path = path
            scene.duration_sec = duration
            audio_files.append(path)

        combined = workspace.combined_audio_path(job.id)
        await asyncio.to_thread(_concat_audio, audio_files, combined)
        job.combined_audio_path = combined
        job.mark_awaiting(Stage.AUDIO)
        await jobs.save(job)

        publish_bot_event(
            event_type=BotEventType.AUDIO_READY,
            job_id=job.id,
            chat_id=job.chat_id,
            payload={"audio_path": combined, "scene_files": audio_files},
        )
        return job.id

    return await _with_jobs(_inner)


async def _generate_images(job_id: str) -> str:
    workspace = TempWorkspaceManager()
    images = PollinationsImageGenerator()

    async def _inner(jobs: MongoJobRepository) -> str:
        job = await jobs.get(job_id)
        if not job or not job.script:
            raise ExternalServiceError("Job has no script for image prompts")
        job.mark_processing(Stage.IMAGES)
        await jobs.save(job)
        workspace.prepare(job.id)

        paths: list[str] = []
        for scene in job.script.scenes:
            path = workspace.image_path(job.id, scene.index)
            await images.generate(prompt=scene.image_prompt, output_path=path)
            scene.image_path = path
            paths.append(path)

        job.mark_awaiting(Stage.IMAGES)
        await jobs.save(job)
        publish_bot_event(
            event_type=BotEventType.IMAGES_READY,
            job_id=job.id,
            chat_id=job.chat_id,
            payload={"image_paths": paths},
        )
        return job.id

    return await _with_jobs(_inner)


async def _assemble_video(job_id: str) -> str:
    workspace = TempWorkspaceManager()
    renderer = FFmpegVideoRenderer()

    async def _inner(jobs: MongoJobRepository) -> str:
        job = await jobs.get(job_id)
        if not job or not job.script:
            raise ExternalServiceError("Job is missing script/media")
        job.mark_processing(Stage.VIDEO)
        await jobs.save(job)

        image_paths = [s.image_path for s in job.script.scenes if s.image_path]
        audio_paths = [s.audio_path for s in job.script.scenes if s.audio_path]
        if not image_paths or not audio_paths:
            raise ExternalServiceError("Missing scene media for assembly")

        output = workspace.video_path(job.id)
        await renderer.assemble(
            job=job,
            image_paths=image_paths,
            audio_paths=audio_paths,
            output_path=output,
        )
        job.video_path = output
        job.mark_completed()
        await jobs.save(job)

        publish_bot_event(
            event_type=BotEventType.VIDEO_READY,
            job_id=job.id,
            chat_id=job.chat_id,
            payload={"video_path": output, "title": job.script.title if job.script else ""},
        )
        # Final product is sent to Telegram first; cleanup is delayed slightly
        # so the bot can open the file. The listener enqueues wipe after send.
        return job.id

    return await _with_jobs(_inner)


async def _fail_job(job_id: str, message: str) -> None:
    async def _inner(jobs: MongoJobRepository) -> None:
        job = await jobs.get(job_id)
        if not job:
            return
        if job.status == JobStatus.PROCESSING:
            job.mark_failed(message)
            await jobs.save(job)
            publish_bot_event(
                event_type=BotEventType.STAGE_FAILED,
                job_id=job.id,
                chat_id=job.chat_id,
                payload={"error": message, "stage": job.stage.value},
            )

    await _with_jobs(_inner)


def _concat_audio(files: list[str], output: str) -> None:
    import ffmpeg

    if len(files) == 1:
        import shutil

        shutil.copyfile(files[0], output)
        return

    inputs = [ffmpeg.input(f) for f in files]
    (
        ffmpeg.filter(inputs, "concat", n=len(inputs), v=0, a=1)
        .output(output)
        .overwrite_output()
        .run(quiet=True)
    )
