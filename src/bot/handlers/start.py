from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards.inline import mode_selection_keyboard
from src.bot.states.video_states import VideoCreationStates

router = Router(name="start")

_WELCOME = (
    "🎬 <b>YouTube Video Generator</b>\n\n"
    "I turn a topic — or your own script — into a fully rendered, "
    "publish-ready video: voiceover, AI images and/or real stock clips, "
    "captions, transitions and background music. I pause for your "
    "approval before each expensive step.\n\n"
    "Use /new_video to start, or /cancel at any time to stop the current job."
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(_WELCOME)


@router.message(Command("new_video"))
async def cmd_new_video(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(VideoCreationStates.waiting_for_mode_choice)
    await message.answer(
        "How do you want to start?",
        reply_markup=mode_selection_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    video_id = data.get("video_id")
    await state.clear()

    if video_id:
        from src.database.repository import VideoRepositoryAsync
        from src.config.constants import VideoStatus
        from src.utils.file_manager import JobWorkspace

        await VideoRepositoryAsync.set_status(video_id, VideoStatus.CANCELLED)
        JobWorkspace.cleanup_by_id(video_id)

    await message.answer("❌ Current job cancelled and temp files cleaned up.")
