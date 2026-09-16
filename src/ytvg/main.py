from __future__ import annotations

import asyncio
import logging

from ytvg.config import get_settings
from ytvg.infrastructure.db.mongo import Mongo
from ytvg.logging import setup_logging
from ytvg.presentation.bot import build_runtime


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to start the bot")
    setup_logging(settings.log_level)
    logger = logging.getLogger("ytvg")

    mongo = Mongo(settings)
    await mongo.connect()
    bot, dp, listener, redis = build_runtime(settings, mongo)

    listener_task = asyncio.create_task(listener.run(), name="bot-event-listener")
    logger.info("Bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        listener_task.cancel()
        await bot.session.close()
        await redis.aclose()
        await mongo.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
