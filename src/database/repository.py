"""
Repository layer — every read/write to the `videos` collection goes through
here so the DB access pattern (async vs sync) stays isolated from business
logic in bot handlers and Celery tasks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.config.constants import VideoStatus
from src.database.connection import get_async_db, get_sync_collection
from src.database.models.video import VideoJob


class VideoRepositoryAsync:
    """Used by the aiogram bot (async)."""

    @staticmethod
    async def create(job: VideoJob) -> VideoJob:
        db = get_async_db()
        await db.videos.insert_one(job.to_mongo())
        return job

    @staticmethod
    async def get(video_id: str) -> VideoJob | None:
        db = get_async_db()
        doc = await db.videos.find_one({"video_id": video_id})
        return VideoJob.from_mongo(doc) if doc else None

    @staticmethod
    async def update(video_id: str, fields: dict[str, Any]) -> None:
        db = get_async_db()
        fields["updated_at"] = datetime.now(timezone.utc)
        await db.videos.update_one({"video_id": video_id}, {"$set": fields})

    @staticmethod
    async def set_status(video_id: str, status: VideoStatus) -> None:
        await VideoRepositoryAsync.update(video_id, {"status": status.value})


class VideoRepositorySync:
    """Used by Celery tasks (sync, pymongo)."""

    @staticmethod
    def get(video_id: str) -> VideoJob | None:
        col = get_sync_collection("videos")
        doc = col.find_one({"video_id": video_id})
        return VideoJob.from_mongo(doc) if doc else None

    @staticmethod
    def update(video_id: str, fields: dict[str, Any]) -> None:
        col = get_sync_collection("videos")
        fields["updated_at"] = datetime.now(timezone.utc)
        col.update_one({"video_id": video_id}, {"$set": fields})

    @staticmethod
    def set_status(video_id: str, status: VideoStatus, error_message: str | None = None) -> None:
        fields: dict[str, Any] = {"status": status.value}
        if error_message is not None:
            fields["error_message"] = error_message
        VideoRepositorySync.update(video_id, fields)
