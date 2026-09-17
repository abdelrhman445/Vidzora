from aiogram import Router

from src.bot.handlers.start import router as start_router
from src.bot.handlers.mode_selection import router as mode_selection_router
from src.bot.handlers.video_flow import router as video_flow_router
from src.bot.handlers.approval import router as approval_router

main_router = Router(name="main")
main_router.include_router(start_router)
main_router.include_router(mode_selection_router)
main_router.include_router(video_flow_router)
main_router.include_router(approval_router)
