from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ytvg.application.pipeline import PipelineService
from ytvg.domain.exceptions import DomainError
from ytvg.presentation.fsm import PipelineSG

router = Router(name="commands")

_APPROVAL_STATES = {
    PipelineSG.awaiting_script.state,
    PipelineSG.awaiting_audio.state,
    PipelineSG.awaiting_images.state,
}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(PipelineSG.collecting_prompt)
    await message.answer(
        "Send a topic or prompt and I will draft a structured video script.\n\n"
        "Each expensive step (script → audio → images → render) waits for your approval.\n"
        "Commands: /new  /cancel  /status"
    )


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PipelineSG.collecting_prompt)
    await message.answer("What should the video be about?")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, pipeline: PipelineService) -> None:
    data = await state.get_data()
    job_id = data.get("job_id")
    if job_id:
        try:
            await pipeline.cancel(job_id)
        except DomainError:
            pass
    await state.clear()
    await state.set_state(PipelineSG.idle)
    await message.answer("Job cancelled. Send /new to start over.")


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current = await state.get_state()
    await message.answer(
        f"FSM: `{current}`\nJob: `{data.get('job_id', 'none')}`",
        parse_mode="Markdown",
    )


@router.message(PipelineSG.collecting_prompt, F.text)
async def on_prompt(message: Message, state: FSMContext, pipeline: PipelineService) -> None:
    prompt = (message.text or "").strip()
    if len(prompt) < 8:
        await message.answer("Please send a more specific topic (at least 8 characters).")
        return
    user_id = message.from_user.id if message.from_user else message.chat.id
    try:
        job = await pipeline.start_job(chat_id=message.chat.id, user_id=user_id, prompt=prompt)
    except DomainError as exc:
        await message.answer(str(exc))
        return

    await state.set_state(PipelineSG.processing)
    await state.update_data(job_id=job.id)
    await message.answer("Generating a structured script. I'll ping you when it's ready for review.")


@router.message(PipelineSG.processing)
async def on_busy(message: Message) -> None:
    await message.answer("Still working on the current stage. Please wait for the approval buttons.")


@router.message(F.text)
async def on_unsolicited_text(
    message: Message, state: FSMContext, pipeline: PipelineService
) -> None:
    current = await state.get_state()
    if current in _APPROVAL_STATES:
        await message.answer(
            "Use the inline buttons under the last preview to Continue, Regenerate, or Cancel."
        )
        return
    await state.set_state(PipelineSG.collecting_prompt)
    await on_prompt(message, state, pipeline)
