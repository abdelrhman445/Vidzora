from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from ytvg.application.pipeline import PipelineService
from ytvg.infrastructure.db.repositories import MongoJobRepository
from ytvg.infrastructure.messaging.celery_dispatcher import CeleryTaskDispatcher
from ytvg.infrastructure.storage.temp_manager import TempWorkspaceManager


class ContainerMiddleware(BaseMiddleware):
    """Injects application services into handler data."""

    def __init__(self, jobs: MongoJobRepository, workspace: TempWorkspaceManager) -> None:
        self._jobs = jobs
        self._workspace = workspace
        self._tasks = CeleryTaskDispatcher()
        self._pipeline = PipelineService(jobs, self._tasks, workspace)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        data["jobs"] = self._jobs
        data["pipeline"] = self._pipeline
        data["workspace"] = self._workspace
        return await handler(event, data)
