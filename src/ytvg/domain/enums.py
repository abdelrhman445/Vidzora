from enum import Enum


class Stage(str, Enum):
    INIT = "init"
    SCRIPT = "script"
    AUDIO = "audio"
    IMAGES = "images"
    VIDEO = "video"
    DONE = "done"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ApprovalAction(str, Enum):
    CONTINUE = "continue"
    REGENERATE = "regenerate"
    CANCEL = "cancel"


class BotEventType(str, Enum):
    SCRIPT_READY = "script_ready"
    AUDIO_READY = "audio_ready"
    IMAGES_READY = "images_ready"
    VIDEO_READY = "video_ready"
    STAGE_FAILED = "stage_failed"
    JOB_CANCELLED = "job_cancelled"
