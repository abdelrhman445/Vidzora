"""Static constants — no secrets, no environment-dependent values."""
from enum import StrEnum


class VideoStatus(StrEnum):
    CREATED = "created"

    SCRIPT_GENERATING = "script_generating"
    SCRIPT_PENDING_APPROVAL = "script_pending_approval"
    SCRIPT_APPROVED = "script_approved"

    AUDIO_GENERATING = "audio_generating"
    AUDIO_PENDING_APPROVAL = "audio_pending_approval"
    AUDIO_APPROVED = "audio_approved"

    IMAGES_GENERATING = "images_generating"
    IMAGES_PENDING_APPROVAL = "images_pending_approval"
    IMAGES_APPROVED = "images_approved"

    RENDERING = "rendering"
    COMPLETED = "completed"

    CANCELLED = "cancelled"
    FAILED = "failed"


class ApprovalAction(StrEnum):
    CONTINUE = "continue"
    REGENERATE = "regenerate"
    CANCEL = "cancel"


class PipelineStage(StrEnum):
    SCRIPT = "script"
    AUDIO = "audio"
    IMAGES = "images"
    RENDER = "render"


class SourceType(StrEnum):
    """Where the scene script came from — drives whether the Script
    approval gate is shown at all."""
    AI_GENERATED = "ai_generated"
    CUSTOM_SCRIPT = "custom_script"


class MediaType(StrEnum):
    """Per-scene visual type — the pipeline can mix both in one video."""
    IMAGE = "image"
    VIDEO = "video"


# callback_data format: "approve:{stage}:{action}:{video_id}"
CALLBACK_PREFIX = "approve"
MODE_CALLBACK_PREFIX = "mode"
MAX_TELEGRAM_CAPTION_LEN = 1024
