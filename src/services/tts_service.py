"""
Text-to-speech via edge-tts (free, Microsoft Edge neural voices).
edge-tts's public API is async, so we wrap each call with asyncio.run()
to expose a plain synchronous function Celery tasks can call directly.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

from src.config.settings import settings


async def _synthesize(text: str, out_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(out_path))


def generate_speech(text: str, out_path: Path, voice: str | None = None) -> float:
    """
    Synthesizes `text` to `out_path` (mp3) and returns the resulting
    audio duration in seconds (needed to time each scene in the render step).
    """
    voice = voice or settings.TTS_VOICE
    asyncio.run(_synthesize(text, out_path, voice))
    audio = MP3(str(out_path))
    return float(audio.info.length)
