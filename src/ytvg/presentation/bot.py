from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from ytvg.application.pipeline import PipelineService
from ytvg.config import Settings
from ytvg.infrastructure.db.mongo import Mongo
from ytvg.infrastructure.db.repositories import MongoJobRepository
from ytvg.infrastructure.messaging.celery_dispatcher import CeleryTaskDispatcher
from ytvg.infrastructure.messaging.redis_bus import RedisEventBus
from ytvg.infrastructure.storage.temp_manager import TempWorkspaceManager
from ytvg.presentation.handlers.callbacks import router as approvals_router
from ytvg.presentation.handlers.commands import router as commands_router
from ytvg.presentation.listener import BotEventListener
from ytvg.presentation.middlewares import ContainerMiddleware


def create_dispatcher(
    settings: Settings,
    jobs: MongoJobRepository,
    workspace: TempWorkspaceManager,
) -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)
    dp.update.middleware(ContainerMiddleware(jobs, workspace))
    dp.include_router(commands_router)
    dp.include_router(approvals_router)
    return dp


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_runtime(settings: Settings, mongo: Mongo):
    jobs = MongoJobRepository(mongo.db)
    workspace = TempWorkspaceManager(settings)
    pipeline = PipelineService(jobs, CeleryTaskDispatcher(), workspace)
    bot = create_bot(settings)
    dp = create_dispatcher(settings, jobs, workspace)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    bus = RedisEventBus(redis, settings.bot_event_channel)
    listener = BotEventListener(bot, dp, bus, pipeline)
    return bot, dp, listener, redis
