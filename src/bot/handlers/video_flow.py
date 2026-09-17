"""
Entry points of the pipeline:
  - AI mode: user sends a topic -> Gemini writes the script (Script gate shown).
  - Custom-script mode: user pastes their own script -> Gemini only segments
    it into scenes (wording untouched) and the pipeline jumps straight into
    audio generation, skipping the Script approval gate.

Either way, the actual generation call is dispatched to Celery so the bot
itself never blocks. The FSM only tracks *where* the user is in the
conversation; the Mongo document is the source of truth for pipeline state.
"""
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.states.video_states import VideoCreationStates
from src.config.constants import SourceType, VideoStatus
from src.database.models.video import VideoJob
from src.database.repository import VideoRepositoryAsync

router = Router(name="video_flow")


@router.message(VideoCreationStates.waiting_for_prompt)
async def receive_prompt(message: Message, state: FSMContext) -> None:
    prompt = (message.text or "").strip()
    if not prompt:
        await message.answer("Please send a text topic to continue.")
        return

    job = VideoJob(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        prompt=prompt,
        source_type=SourceType.AI_GENERATED,
    )
    await VideoRepositoryAsync.create(job)
    await VideoRepositoryAsync.set_status(job.video_id, VideoStatus.SCRIPT_GENERATING)

    await state.update_data(video_id=job.video_id)
    await state.set_state(VideoCreationStates.awaiting_script_approval)

    status_msg = await message.answer(
        f"🧠 Generating script for: <i>{prompt}</i>\n⏳ This runs in the background — I'll notify you here."
    )

    from src.celery_app.tasks.script_tasks import generate_script_task

    generate_script_task.delay(job.video_id, status_msg.message_id)


@router.message(VideoCreationStates.waiting_for_custom_script)
async def receive_custom_script(message: Message, state: FSMContext) -> None:
    script_text = (message.text or "").strip()
    if len(script_text) < 20:
        await message.answer("That looks too short to be a full script — please send the complete text.")
        return

    job = VideoJob(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        prompt=script_text,
        source_type=SourceType.CUSTOM_SCRIPT,
    )
    await VideoRepositoryAsync.create(job)
    await VideoRepositoryAsync.set_status(job.video_id, VideoStatus.SCRIPT_GENERATING)

    await state.update_data(video_id=job.video_id)
    await state.set_state(VideoCreationStates.awaiting_audio_approval)  # script gate is skipped

    status_msg = await message.answer(
        "📄 Got your script — splitting it into scenes...\n⏳ I'll notify you here when the voiceover is ready."
    )

    from src.celery_app.tasks.script_tasks import structure_custom_script_task

    structure_custom_script_task.delay(job.video_id, status_msg.message_id)
