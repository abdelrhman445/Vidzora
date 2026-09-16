from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ytvg.application.pipeline import PipelineService
from ytvg.domain.enums import ApprovalAction, Stage
from ytvg.domain.exceptions import DomainError, InvalidJobTransitionError
from ytvg.presentation.fsm import PipelineSG
from ytvg.presentation.keyboards import ApprovalCallback

router = Router(name="approvals")

_NEXT_STATE = {
    Stage.SCRIPT: PipelineSG.processing,  # audio generation starts
    Stage.AUDIO: PipelineSG.processing,
    Stage.IMAGES: PipelineSG.processing,
}


@router.callback_query(ApprovalCallback.filter())
async def on_approval(
    query: CallbackQuery,
    callback_data: ApprovalCallback,
    state: FSMContext,
    pipeline: PipelineService,
) -> None:
    await query.answer()
    action = ApprovalAction(callback_data.action)
    stage = Stage(callback_data.stage)
    job_id = callback_data.job_id

    try:
        if action is ApprovalAction.CANCEL:
            await pipeline.cancel(job_id)
            await state.set_state(PipelineSG.idle)
            await state.clear()
            if query.message:
                await query.message.edit_reply_markup(reply_markup=None)
            await query.message.answer("Cancelled. Temporary files will be wiped. Send /new when ready.")
            return

        if action is ApprovalAction.REGENERATE:
            await pipeline.regenerate(job_id, stage)
            await state.set_state(PipelineSG.processing)
            await state.update_data(job_id=job_id)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=None)
            await query.message.answer(f"Regenerating {stage.value}…")
            return

        await pipeline.approve(job_id, stage)
        await state.set_state(_NEXT_STATE.get(stage, PipelineSG.processing))
        await state.update_data(job_id=job_id)
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
        label = {
            Stage.SCRIPT: "Approved. Generating narration…",
            Stage.AUDIO: "Approved. Generating scene images…",
            Stage.IMAGES: "Approved. Assembling the final video…",
        }.get(stage, "Approved.")
        await query.message.answer(label)
    except InvalidJobTransitionError:
        await query.message.answer(
            "That approval is no longer valid (stale button or job already moved on)."
        )
    except DomainError as exc:
        await query.message.answer(f"Could not apply that action: {exc}")
