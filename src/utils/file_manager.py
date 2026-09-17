"""
Temporary-workspace management.

Every video job gets its own isolated subtree under TEMP_DIR/{video_id}/
so concurrent jobs never collide, and cleanup is a single rmtree call
whether the pipeline succeeds, is cancelled, or fails.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from src.config.settings import settings
from src.utils.logger import logger


class JobWorkspace:
    """Owns the on-disk temp folder for one video job."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.root = settings.TEMP_DIR / video_id
        self.scripts_dir = self.root / "scripts"
        self.audio_dir = self.root / "audio"
        self.images_dir = self.root / "images"
        self.output_dir = self.root / "output"

    def create(self) -> "JobWorkspace":
        for d in (self.scripts_dir, self.audio_dir, self.images_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def script_path(self) -> Path:
        return self.scripts_dir / "script.json"

    def audio_path(self, scene_number: int) -> Path:
        return self.audio_dir / f"scene_{scene_number:03d}.mp3"

    def image_path(self, scene_number: int) -> Path:
        return self.images_dir / f"scene_{scene_number:03d}.png"

    def video_dir_path(self, scene_number: int) -> Path:
        return self.images_dir / f"scene_{scene_number:03d}.mp4"

    def output_path(self) -> Path:
        return self.output_dir / f"{self.video_id}_final.mp4"

    def cleanup(self) -> None:
        """Wipe this job's entire temp subtree. Safe to call multiple times."""
        if self.root.exists():
            try:
                shutil.rmtree(self.root)
                logger.info(f"[{self.video_id}] Cleaned up temp workspace: {self.root}")
            except OSError as exc:
                logger.warning(f"[{self.video_id}] Failed to clean up {self.root}: {exc}")

    @staticmethod
    def cleanup_by_id(video_id: str) -> None:
        JobWorkspace(video_id).cleanup()

    @staticmethod
    def purge_orphaned(max_age_hours: int = 24) -> None:
        """
        Safety-net sweep (run periodically via Celery beat) that removes
        any job folder older than max_age_hours — catches temp dirs left
        behind by crashed workers that never hit the normal cleanup path.
        """
        import time

        cutoff = time.time() - max_age_hours * 3600
        if not settings.TEMP_DIR.exists():
            return
        for child in settings.TEMP_DIR.iterdir():
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                logger.info(f"Purged orphaned temp dir: {child}")
