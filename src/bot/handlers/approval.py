"""
Handles every Approval Gateway button press.
This is the sole place that decides, per (stage, action), whether to
dispatch the next Celery task, re-dispatch the current one, or cancel
and clean up. Keeping that decision table in one router avoids
duplicated branching scattered across per-stage handlers.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.states.video_states import VideoCreationStates
from src.config.constants import ApprovalAction, CALLBACK_PREFIX, PipelineStage, VideoStatus
from src.database.repository import VideoRepositoryAsync
from src.utils.file_manager import JobWorkspace

router = Router(name="approval")

_NEXT_STATE = {
    PipelineStage.SCRIPT: VideoCreationStates.awaiting_audio_approval,
    PipelineStage.AUDIO: VideoCreationStates.awaiting_images_approval,
    PipelineStage.IMAGES: VideoCreationStates.rendering,
}


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def handle_approval(callback: CallbackQuery, state: FSMContext) -> None:
    _, stage_raw, action_raw, video_id = callback.data.split(":")
    stage, action = PipelineStage(stage_raw), ApprovalAction(action_raw)

    job = await VideoRepositoryAsync.get(video_id)
    if job is None:
        await callback.answer("This job no longer exists.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)  # prevent double taps

    if action == ApprovalAction.CANCEL:
        await VideoRepositoryAsync.set_status(video_id, VideoStatus.CANCELLED)
        JobWorkspace.cleanup_by_id(video_id)
        await state.clear()
        await callback.message.answer("❌ Job cancelled. Temp files cleaned up.")
        await callback.answer()
        return

    if action == ApprovalAction.REGENERATE:
        await callback.message.answer(f"🔄 Regenerating {stage.value}...")
        _dispatch_stage(stage, video_id, callback.message.message_id)
        await callback.answer()
        return

    # CONTINUE -> advance to next stage
    await callback.answer()
    next_stage = _next_stage_after(stage)
    if next_stage is None:
        # Approving IMAGES triggers final render (no further approval gate after it).
        await callback.message.answer("🎬 All assets approved — rendering final video...")
        _dispatch_stage(PipelineStage.RENDER, video_id, callback.message.message_id)
        await state.set_state(VideoCreationStates.rendering)
        return

    await callback.message.answer(f"✅ Approved. Starting {next_stage.value} generation...")
    _dispatch_stage(next_stage, video_id, callback.message.message_id)
    await state.set_state(_NEXT_STATE[stage])


def _next_stage_after(stage: PipelineStage) -> PipelineStage | None:
    order = [PipelineStage.SCRIPT, PipelineStage.AUDIO, PipelineStage.IMAGES]
    idx = order.index(stage)
    return order[idx + 1] if idx + 1 < len(order) else None


def _dispatch_stage(stage: PipelineStage, video_id: str, reply_to_message_id: int) -> None:
    if stage == PipelineStage.SCRIPT:
        from src.celery_app.tasks.script_tasks import generate_script_task
        generate_script_task.delay(video_id, reply_to_message_id)
    elif stage == PipelineStage.AUDIO:
        from src.celery_app.tasks.audio_tasks import generate_audio_task
        generate_audio_task.delay(video_id, reply_to_message_id)
    elif stage == PipelineStage.IMAGES:
        from src.celery_app.tasks.image_tasks import generate_images_task
        generate_images_task.delay(video_id, reply_to_message_id)
    elif stage == PipelineStage.RENDER:
        from src.celery_app.tasks.render_tasks import render_video_task
        render_video_task.delay(video_id, reply_to_message_id)
