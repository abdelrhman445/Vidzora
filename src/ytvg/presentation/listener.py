from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import FSInputFile, InputMediaPhoto

from ytvg.application.dto import BotEvent
from ytvg.application.pipeline import PipelineService
from ytvg.domain.enums import BotEventType, Stage
from ytvg.infrastructure.messaging.redis_bus import RedisEventBus
from ytvg.presentation.fsm import PipelineSG
from ytvg.presentation.keyboards import approval_keyboard

logger = logging.getLogger(__name__)


class BotEventListener:
    """Consumes worker events and presents the next approval gateway to the user."""

    def __init__(
        self,
        bot: Bot,
        dispatcher: Dispatcher,
        bus: RedisEventBus,
        pipeline: PipelineService,
    ) -> None:
        self._bot = bot
        self._dp = dispatcher
        self._bus = bus
        self._pipeline = pipeline

    async def run(self) -> None:
        async for event in self._bus.subscribe():
            try:
                await self._handle(event)
            except Exception:
                logger.exception("Failed to handle bot event %s", event)

    async def _handle(self, event: BotEvent) -> None:
        handlers = {
            BotEventType.SCRIPT_READY: self._on_script,
            BotEventType.AUDIO_READY: self._on_audio,
            BotEventType.IMAGES_READY: self._on_images,
            BotEventType.VIDEO_READY: self._on_video,
            BotEventType.STAGE_FAILED: self._on_failed,
        }
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)

    async def _set_state(self, chat_id: int, user_id: int, state, job_id: str) -> None:
        key = StorageKey(bot_id=self._bot.id, chat_id=chat_id, user_id=user_id)
        await self._dp.fsm.storage.set_state(key, state)
        await self._dp.fsm.storage.set_data(key, {"job_id": job_id})

    async def _on_script(self, event: BotEvent) -> None:
        job = await self._pipeline.get_job(event.job_id)
        if not job or not job.script:
            return
        lines = [f"<b>{job.script.title}</b>", job.script.description, ""]
        for scene in job.script.scenes:
            lines.append(f"<b>Scene {scene.index}</b>")
            lines.append(scene.voiceover)
            lines.append(f"<i>Image:</i> {scene.image_prompt}")
            lines.append("")
        text = "\n".join(lines).strip()
        if len(text) > 3900:
            text = text[:3900] + "\n…"
        await self._bot.send_message(
    event.chat_id,
    text,
    reply_markup=approval_keyboard(job.id, Stage.SCRIPT),
)
        await self._set_state(event.chat_id, job.user_id, PipelineSG.awaiting_script, job.id)

    async def _on_audio(self, event: BotEvent) -> None:
        job = await self._pipeline.get_job(event.job_id)
        if not job:
            return
        audio = event.payload.get("audio_path") or job.combined_audio_path
        if audio and Path(audio).exists():
            await self._bot.send_audio(
                event.chat_id,
                audio=FSInputFile(audio),
                caption="Narration preview. Continue to generate images?",
                reply_markup=approval_keyboard(job.id, Stage.AUDIO),
            )
        else:
            await self._bot.send_message(
                event.chat_id,
                "Audio generated, but the preview file is missing.",
                reply_markup=approval_keyboard(job.id, Stage.AUDIO),
            )
        await self._set_state(event.chat_id, job.user_id, PipelineSG.awaiting_audio, job.id)

    async def _on_images(self, event: BotEvent) -> None:
        job = await self._pipeline.get_job(event.job_id)
        if not job:
            return
        paths = [p for p in event.payload.get("image_paths", []) if Path(p).exists()]
        if paths:
            media = [InputMediaPhoto(media=FSInputFile(p)) for p in paths[:10]]
            await self._bot.send_media_group(event.chat_id, media=media)
        await self._bot.send_message(
            event.chat_id,
            "Scene images ready. Assemble the final video?",
            reply_markup=approval_keyboard(job.id, Stage.IMAGES),
        )
        await self._set_state(event.chat_id, job.user_id, PipelineSG.awaiting_images, job.id)

    async def _on_video(self, event: BotEvent) -> None:
        job = await self._pipeline.get_job(event.job_id)
        if not job:
            return
        video = event.payload.get("video_path") or job.video_path
        caption = event.payload.get("title") or "Your video"
        if video and Path(video).exists():
            await self._bot.send_video(
                event.chat_id,
                video=FSInputFile(video),
                caption=f"{caption}\n\nDone. Cleaning up temporary files.",
            )
        else:
            await self._bot.send_message(event.chat_id, "Render finished but the MP4 was not found.")
        self._pipeline.enqueue_cleanup(job.id)
        key = StorageKey(bot_id=self._bot.id, chat_id=event.chat_id, user_id=job.user_id)
        await self._dp.fsm.storage.set_state(key, PipelineSG.idle)
        await self._dp.fsm.storage.set_data(key, {})

    async def _on_failed(self, event: BotEvent) -> None:
        stage = event.payload.get("stage", "unknown")
        error = event.payload.get("error", "unknown error")
        await self._bot.send_message(
            event.chat_id,
            f"Stage <b>{stage}</b> failed:\n<code>{error[:1500]}</code>\n\nSend /new to retry.",
            parse_mode="HTML",
        )
