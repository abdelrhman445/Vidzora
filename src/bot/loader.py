"""
Single shared Bot/Dispatcher instances for the aiogram process.
Storage is Redis-backed so FSM state survives bot restarts and is
inspectable/shareable if you ever scale to multiple bot instances.
"""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from src.config.settings import settings

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

storage = RedisStorage.from_url(settings.REDIS_URL)
dp = Dispatcher(storage=storage)
