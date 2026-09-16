from __future__ import annotations

import json
import logging

from redis.asyncio import Redis

from ytvg.application.dto import BotEvent
from ytvg.domain.enums import BotEventType

logger = logging.getLogger(__name__)


class RedisEventBus:
    """Pub/Sub bridge from Celery workers back into the long-polling bot process."""

    def __init__(self, redis: Redis, channel: str) -> None:
        self._redis = redis
        self._channel = channel

    async def publish(
        self,
        *,
        event_type: BotEventType,
        job_id: str,
        chat_id: int,
        payload: dict | None = None,
    ) -> None:
        event = BotEvent(
            event_type=event_type,
            job_id=job_id,
            chat_id=chat_id,
            payload=payload or {},
        )
        await self._redis.publish(self._channel, event.model_dump_json())
        logger.info("Published %s for job %s", event_type, job_id)

    async def subscribe(self):
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    yield BotEvent.model_validate(json.loads(data))
                except Exception:
                    logger.exception("Invalid bot event payload: %s", data)
        finally:
            await pubsub.unsubscribe(self._channel)
            await pubsub.aclose()
