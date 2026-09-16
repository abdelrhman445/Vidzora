from __future__ import annotations

from celery import Celery

from ytvg.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ytvg",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["ytvg.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    task_default_queue="maintenance",
    task_routes={
        "ytvg.workers.tasks.generate_script": {"queue": "text"},
        "ytvg.workers.tasks.generate_audio": {"queue": "audio"},
        "ytvg.workers.tasks.generate_images": {"queue": "images"},
        "ytvg.workers.tasks.assemble_video": {"queue": "video"},
        "ytvg.workers.tasks.cleanup_job": {"queue": "maintenance"},
        "ytvg.workers.tasks.sweep_stale_workspaces": {"queue": "maintenance"},
    },
    beat_schedule={
        "sweep-temp-hourly": {
            "task": "ytvg.workers.tasks.sweep_stale_workspaces",
            "schedule": 3600.0,
        }
    },
)
