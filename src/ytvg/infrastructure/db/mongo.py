from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ytvg.config import Settings, get_settings


class Mongo:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: AsyncIOMotorClient | None = None

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(self._settings.mongodb_uri)
        await self._client.admin.command("ping")
        await self.db.jobs.create_index("user_id")
        await self.db.jobs.create_index("status")
        await self.db.jobs.create_index("updated_at")

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._client is None:
            raise RuntimeError("Mongo is not connected")
        return self._client[self._settings.mongodb_db_name]
