from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import ffmpeg

from ytvg.config import Settings, get_settings
from ytvg.domain.entities import VideoJob
from ytvg.domain.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class FFmpegVideoRenderer:
    """Stitch per-scene stills + TTS into a vertical MP4 without loading everything into RAM."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def assemble(
        self,
        *,
        job: VideoJob,
        image_paths: list[str],
        audio_paths: list[str],
        output_path: str,
    ) -> str:
        if len(image_paths) != len(audio_paths):
            raise ExternalServiceError("Image/audio scene counts do not match")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        scene_clips: list[Path] = []
        work = Path(output_path).parent

        for idx, (image, audio) in enumerate(zip(image_paths, audio_paths, strict=True), start=1):
            clip = work / f"scene_{idx:03d}.mp4"
            await asyncio.to_thread(self._render_scene, image, audio, clip)
            scene_clips.append(clip)

        concat_list = work / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in scene_clips),
            encoding="utf-8",
        )
        await asyncio.to_thread(self._concat, concat_list, Path(output_path))
        logger.info("Assembled video %s", output_path)
        return output_path

    def _render_scene(self, image: str, audio: str, output: Path) -> None:
        s = self._settings
        stream = ffmpeg.output(
            ffmpeg.input(image, loop=1, framerate=s.video_fps),
            ffmpeg.input(audio),
            str(output),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            shortest=None,
            r=s.video_fps,
            s=f"{s.video_width}x{s.video_height}",
            video_bitrate=s.video_bitrate,
            preset="veryfast",
            threads=1,
            movflags="faststart",
        )
        ffmpeg.run(stream, overwrite_output=True, quiet=True)

    @staticmethod
    def _concat(concat_list: Path, output: Path) -> None:
        stream = ffmpeg.input(str(concat_list), format="concat", safe=0)
        stream = ffmpeg.output(stream, str(output), c="copy", movflags="faststart")
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
