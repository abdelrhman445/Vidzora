"""Handles the 🤖 AI-script vs 📝 my-own-script choice from /new_video."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.states.video_states import VideoCreationStates
from src.config.constants import MODE_CALLBACK_PREFIX

router = Router(name="mode_selection")


@router.callback_query(F.data.startswith(f"{MODE_CALLBACK_PREFIX}:"))
async def handle_mode_choice(callback: CallbackQuery, state: FSMContext) -> None:
    _, mode = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    if mode == "ai":
        await state.set_state(VideoCreationStates.waiting_for_prompt)
        await callback.message.answer(
            "What's the video about? Send me a topic, e.g. "
            "<i>\"5 mind-blowing facts about black holes\"</i>."
        )
    else:
        await state.set_state(VideoCreationStates.waiting_for_custom_script)
        await callback.message.answer(
            "Send me your full script as one message. I'll split it into "
            "scenes, generate the voiceover and visuals for it, and skip "
            "straight past the script-approval step since it's already yours."
        )
