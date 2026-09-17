"""Periodic housekeeping tasks (wired into Celery beat)."""
from celery import shared_task

from src.utils.file_manager import JobWorkspace


@shared_task
def purge_orphaned_temp() -> None:
    JobWorkspace.purge_orphaned(max_age_hours=24)
