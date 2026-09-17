"""
Inline keyboard builders for the Approval Gateways.
callback_data is intentionally compact: "approve:{stage}:{action}:{video_id}"
(Telegram caps callback_data at 64 bytes, so video_id is a short hex slug.)
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.constants import ApprovalAction, CALLBACK_PREFIX, MODE_CALLBACK_PREFIX, PipelineStage


def approval_keyboard(stage: PipelineStage, video_id: str) -> InlineKeyboardMarkup:
    def cb(action: ApprovalAction) -> str:
        return f"{CALLBACK_PREFIX}:{stage.value}:{action.value}:{video_id}"

    buttons = [
        [
            InlineKeyboardButton(text="✅ Continue", callback_data=cb(ApprovalAction.CONTINUE)),
            InlineKeyboardButton(text="🔄 Regenerate", callback_data=cb(ApprovalAction.REGENERATE)),
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data=cb(ApprovalAction.CANCEL))],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def mode_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🤖 Write it for me (AI)", callback_data=f"{MODE_CALLBACK_PREFIX}:ai")],
        [InlineKeyboardButton(text="📝 I have my own script", callback_data=f"{MODE_CALLBACK_PREFIX}:custom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
