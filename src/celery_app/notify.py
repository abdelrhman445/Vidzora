"""
Telegram notifications sent *from* Celery tasks (sync worker processes).
aiogram's Bot API is async-only, so each call spins up a short-lived
asyncio event loop via asyncio.run(). This is intentionally simple/stateless
rather than sharing a loop across tasks — Celery workers are sync and
prefork-based, so per-call loops are the safest option here.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

from src.bot.keyboards.inline import approval_keyboard
from src.config.constants import PipelineStage
from src.config.settings import settings


def _get_bot() -> Bot:
    return Bot(token=settings.BOT_TOKEN)


async def _send_text(chat_id: int, text: str, reply_markup=None) -> None:
    bot = _get_bot()
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    finally:
        await bot.session.close()


async def _send_visuals(chat_id: int, media_items: list[tuple[str, str]], caption: str, reply_markup) -> None:
    """media_items: list of (path, 'image'|'video') — a Telegram media
    group can mix photos and videos in one album (max 10 items)."""
    bot = _get_bot()
    try:
        media = []
        for i, (path, kind) in enumerate(media_items[:10]):
            item_caption = caption if i == 0 else None
            if kind == "video":
                media.append(InputMediaVideo(media=FSInputFile(path), caption=item_caption))
            else:
                media.append(InputMediaPhoto(media=FSInputFile(path), caption=item_caption))

        await bot.send_media_group(chat_id, media)
        await bot.send_message(chat_id, "Approve these visuals?", reply_markup=reply_markup)
    finally:
        await bot.session.close()


async def _send_audio_previews(chat_id: int, audio_paths: list[Path], reply_markup) -> None:
    bot = _get_bot()
    try:
        for p in audio_paths:
            await bot.send_audio(chat_id, FSInputFile(str(p)), caption=p.stem)
        await bot.send_message(chat_id, "Approve this voiceover?", reply_markup=reply_markup)
    finally:
        await bot.session.close()


async def _send_video(chat_id: int, video_path: Path, caption: str) -> None:
    bot = _get_bot()
    try:
        await bot.send_video(chat_id, FSInputFile(str(video_path)), caption=caption, supports_streaming=True)
    finally:
        await bot.session.close()


async def _send_error(chat_id: int, text: str) -> None:
    bot = _get_bot()
    try:
        await bot.send_message(chat_id, f"⚠️ {text}")
    finally:
        await bot.session.close()


# --- Public sync wrappers (call these from Celery tasks) ---

def notify_script_ready(chat_id: int, video_id: str, title: str, script_preview: str) -> None:
    text = f"📝 <b>{title}</b>\n\n{script_preview}"
    kb = approval_keyboard(PipelineStage.SCRIPT, video_id)
    asyncio.run(_send_text(chat_id, text, kb))


def notify_audio_ready(chat_id: int, video_id: str, audio_paths: list[Path]) -> None:
    kb = approval_keyboard(PipelineStage.AUDIO, video_id)
    asyncio.run(_send_audio_previews(chat_id, audio_paths, kb))


def notify_visuals_ready(chat_id: int, video_id: str, media_items: list[tuple[str, str]]) -> None:
    kb = approval_keyboard(PipelineStage.IMAGES, video_id)
    asyncio.run(_send_visuals(chat_id, media_items, "🖼️ Generated scene visuals (images + clips)", kb))


def notify_video_ready(chat_id: int, video_path: Path, title: str) -> None:
    asyncio.run(_send_video(chat_id, video_path, f"✅ <b>{title}</b> — done!"))


def notify_error(chat_id: int, message: str) -> None:
    asyncio.run(_send_error(chat_id, message))


def notify_info(chat_id: int, text: str) -> None:
    asyncio.run(_send_text(chat_id, text))
