"""
Async MongoDB connection using Motor.
Single shared client for the whole process (bot side). Celery workers
get their own client via `get_sync_collection` since Celery tasks run
in separate, synchronous worker processes.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.collection import Collection

from src.config.settings import settings

_async_client: AsyncIOMotorClient | None = None
_sync_client: MongoClient | None = None


def get_async_db() -> AsyncIOMotorDatabase:
    """Used by the aiogram bot process (async context)."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncIOMotorClient(settings.MONGO_URI)
    return _async_client[settings.MONGO_DB_NAME]


def get_sync_collection(name: str) -> Collection:
    """Used by Celery tasks (sync context) — pymongo, not motor."""
    global _sync_client
    if _sync_client is None:
        _sync_client = MongoClient(settings.MONGO_URI)
    return _sync_client[settings.MONGO_DB_NAME][name]


async def ensure_indexes() -> None:
    db = get_async_db()
    await db.videos.create_index("video_id", unique=True)
    await db.videos.create_index("chat_id")
    await db.videos.create_index("status")
