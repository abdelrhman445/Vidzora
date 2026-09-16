from __future__ import annotations

import logging
from pathlib import Path

import edge_tts

from ytvg.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EdgeTTSSynthesizer:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def synthesize_scene(
        self, *, text: str, output_path: str, voice: str | None = None
    ) -> float:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice or self._settings.tts_voice,
            rate=self._settings.tts_rate,
        )
        await communicate.save(output_path)
        duration = await _probe_duration(output_path)
        logger.info("Wrote TTS %s (%.2fs)", output_path, duration)
        return duration


async def _probe_duration(path: str) -> float:
    """Best-effort duration via mutagen-free MP3 frame scan using edge_tts metadata.

    Falls back to 0.0; the renderer uses ffprobe later if needed.
    """
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return float(result.stdout.strip() or 0.0)
    except Exception:
        return 0.0
