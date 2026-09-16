"""Temporary workspace management for per-job media artifacts.

Every job owns an isolated directory under `TEMP_DIR`:

    temp/<job_id>/
        audio/scene_001.mp3
        images/scene_001.png
        video/output.mp4
        combined.mp3

`TempWorkspaceManager.wipe` is called after successful assembly **and** on
cancel/failure so `/temp` never accumulates orphaned files. A TTL sweeper
removes abandoned workspaces whose mtime is older than `TEMP_TTL_HOURS`.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import time
from pathlib import Path

from ytvg.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TempWorkspaceManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._root = Path(self._settings.temp_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        self._assert_safe_id(job_id)
        return self._root / job_id

    def prepare(self, job_id: str) -> str:
        path = self.job_dir(job_id)
        (path / "audio").mkdir(parents=True, exist_ok=True)
        (path / "images").mkdir(parents=True, exist_ok=True)
        (path / "video").mkdir(parents=True, exist_ok=True)
        logger.info("Prepared workspace %s", path)
        return str(path)

    def audio_path(self, job_id: str, scene_index: int) -> str:
        return str(self.job_dir(job_id) / "audio" / f"scene_{scene_index:03d}.mp3")

    def image_path(self, job_id: str, scene_index: int) -> str:
        return str(self.job_dir(job_id) / "images" / f"scene_{scene_index:03d}.png")

    def combined_audio_path(self, job_id: str) -> str:
        return str(self.job_dir(job_id) / "combined.mp3")

    def video_path(self, job_id: str) -> str:
        return str(self.job_dir(job_id) / "video" / "output.mp4")

    def wipe(self, job_id: str) -> None:
        path = self.job_dir(job_id)
        if not path.exists():
            return
        self._rmtree(path)
        logger.info("Wiped workspace %s", path)

    def wipe_all_stale(self) -> int:
        ttl = self._settings.temp_ttl_hours * 3600
        now = time.time()
        removed = 0
        if not self._root.exists():
            return 0
        for child in self._root.iterdir():
            if not child.is_dir():
                continue
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            if now - mtime > ttl:
                self._rmtree(child)
                removed += 1
        if removed:
            logger.info("Swept %s stale workspaces from %s", removed, self._root)
        return removed

    def wipe_root(self) -> None:
        """Nuclear option: delete every job workspace. Used in tests."""
        if self._root.exists():
            self._rmtree(self._root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _rmtree(self, path: Path) -> None:
        def _onerror(func, target, _exc) -> None:  # noqa: ANN001
            try:
                os.chmod(target, stat.S_IWRITE)
                func(target)
            except OSError as exc:
                logger.warning("Failed to remove %s: %s", target, exc)

        shutil.rmtree(path, onerror=_onerror)

    @staticmethod
    def _assert_safe_id(job_id: str) -> None:
        if not job_id or ".." in job_id or "/" in job_id or "\\" in job_id:
            raise ValueError(f"Unsafe job_id for filesystem path: {job_id!r}")
