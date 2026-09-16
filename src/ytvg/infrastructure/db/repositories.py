from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from ytvg.domain.entities import VideoJob
from ytvg.domain.enums import JobStatus


class MongoJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db.jobs

    async def create(self, job: VideoJob) -> VideoJob:
        await self._col.insert_one(job.model_dump(mode="python"))
        return job

    async def get(self, job_id: str) -> VideoJob | None:
        doc = await self._col.find_one({"id": job_id}, {"_id": 0})
        return VideoJob.model_validate(doc) if doc else None

    async def save(self, job: VideoJob) -> VideoJob:
        await self._col.replace_one({"id": job.id}, job.model_dump(mode="python"), upsert=True)
        return job

    async def find_active_for_user(self, user_id: int) -> VideoJob | None:
        doc = await self._col.find_one(
            {
                "user_id": user_id,
                "status": {
                    "$in": [
                        JobStatus.PENDING.value,
                        JobStatus.PROCESSING.value,
                        JobStatus.AWAITING_APPROVAL.value,
                    ]
                },
            },
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        return VideoJob.model_validate(doc) if doc else None

    async def list_by_status(self, status: JobStatus, limit: int = 50) -> list[VideoJob]:
        cursor = self._col.find({"status": status.value}, {"_id": 0}).limit(limit)
        return [VideoJob.model_validate(doc) async for doc in cursor]
