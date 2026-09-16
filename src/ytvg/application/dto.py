from __future__ import annotations

from pydantic import BaseModel, Field

from ytvg.domain.enums import BotEventType, Stage


class BotEvent(BaseModel):
    """Message published by workers and consumed by the Telegram process."""

    event_type: BotEventType
    job_id: str
    chat_id: int
    payload: dict = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    job_id: str
    stage: Stage
    action: str
