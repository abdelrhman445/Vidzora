from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ytvg.domain.enums import ApprovalAction, Stage


class ApprovalCallback(CallbackData, prefix="appr"):
    action: str
    job_id: str
    stage: str


def approval_keyboard(job_id: str, stage: Stage) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Continue",
        callback_data=ApprovalCallback(
            action=ApprovalAction.CONTINUE.value, job_id=job_id, stage=stage.value
        ),
    )
    builder.button(
        text="Regenerate",
        callback_data=ApprovalCallback(
            action=ApprovalAction.REGENERATE.value, job_id=job_id, stage=stage.value
        ),
    )
    builder.button(
        text="Cancel",
        callback_data=ApprovalCallback(
            action=ApprovalAction.CANCEL.value, job_id=job_id, stage=stage.value
        ),
    )
    builder.adjust(2, 1)
    return builder.as_markup()
