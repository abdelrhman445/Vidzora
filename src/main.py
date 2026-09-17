"""
Bot process entry point.
Run with: python -m src.main
(The Celery worker is a completely separate process — see README.)
"""
import asyncio

from src.celery_app.celery import celery_app  # noqa: F401 — must import before any .delay() calls
from src.bot.handlers import main_router
from src.bot.loader import bot, dp
from src.database.connection import ensure_indexes
from src.utils.logger import logger


async def main() -> None:
    dp.include_router(main_router)
    await ensure_indexes()

    logger.info("Bot starting — dropping pending updates and polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")