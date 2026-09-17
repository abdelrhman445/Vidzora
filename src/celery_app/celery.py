"""
Celery application definition.
Run the worker with:
    celery -A src.celery_app.celery worker --loglevel=info -Q video_pipeline
Run beat (for the orphaned-temp-file sweep) with:
    celery -A src.celery_app.celery beat --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

celery_app = Celery(
    "youtube_automation_bot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "src.celery_app.tasks.script_tasks",
        "src.celery_app.tasks.audio_tasks",
        "src.celery_app.tasks.image_tasks",
        "src.celery_app.tasks.render_tasks",
        "src.celery_app.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_default_queue="video_pipeline",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # one heavy job at a time per worker process
    task_time_limit=60 * 30,        # hard kill after 30 min (rendering can be slow)
    task_soft_time_limit=60 * 25,
    beat_schedule={
        "purge-orphaned-temp-dirs": {
            "task": "src.celery_app.tasks.maintenance.purge_orphaned_temp",
            "schedule": crontab(minute=0),  # hourly
        },
    },
)
