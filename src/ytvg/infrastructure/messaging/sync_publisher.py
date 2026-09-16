"""Sync Redis publisher used inside Celery workers (no running event loop)."""

from __future__ import annotations

import json
import logging

import redis

from ytvg.config import get_settings
from ytvg.domain.enums import BotEventType

logger = logging.getLogger(__name__)


def publish_bot_event(
    *,
    event_type: BotEventType,
    job_id: str,
    chat_id: int,
    payload: dict | None = None,
) -> None:
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    body = json.dumps(
        {
            "event_type": event_type.value,
            "job_id": job_id,
            "chat_id": chat_id,
            "payload": payload or {},
        }
    )
    client.publish(settings.bot_event_channel, body)
    logger.info("Worker published %s for job %s", event_type, job_id)
