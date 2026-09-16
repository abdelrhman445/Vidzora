import pytest

from ytvg.application.pipeline import PipelineService
from ytvg.config import Settings
from ytvg.domain.enums import JobStatus, Stage
from ytvg.domain.exceptions import ActiveJobExistsError, InvalidJobTransitionError
from ytvg.infrastructure.storage.temp_manager import TempWorkspaceManager
from tests.fakes import InMemoryJobRepository, RecordingDispatcher


@pytest.fixture
def pipeline(tmp_path):
    jobs = InMemoryJobRepository()
    tasks = RecordingDispatcher()
    workspace = TempWorkspaceManager(Settings(telegram_bot_token="x", temp_dir=tmp_path))
    return PipelineService(jobs, tasks, workspace), jobs, tasks


@pytest.mark.asyncio
async def test_start_enqueues_script(pipeline):
    svc, _, tasks = pipeline
    job = await svc.start_job(chat_id=1, user_id=42, prompt="Create a video about space")
    assert job.status == JobStatus.PROCESSING
    assert job.stage == Stage.SCRIPT
    assert tasks.calls == [("script", job.id)]


@pytest.mark.asyncio
async def test_cannot_start_second_active_job(pipeline):
    svc, _, _ = pipeline
    await svc.start_job(chat_id=1, user_id=42, prompt="Create a video about space")
    with pytest.raises(ActiveJobExistsError):
        await svc.start_job(chat_id=1, user_id=42, prompt="another topic here")


@pytest.mark.asyncio
async def test_approve_requires_awaiting_state(pipeline):
    svc, _, _ = pipeline
    job = await svc.start_job(chat_id=1, user_id=42, prompt="Create a video about space")
    with pytest.raises(InvalidJobTransitionError):
        await svc.approve(job.id, Stage.SCRIPT)


@pytest.mark.asyncio
async def test_approve_script_enqueues_audio(pipeline):
    svc, jobs, tasks = pipeline
    job = await svc.start_job(chat_id=1, user_id=42, prompt="Create a video about space")
    stored = await jobs.get(job.id)
    stored.mark_awaiting(Stage.SCRIPT)
    await jobs.save(stored)
    updated = await svc.approve(job.id, Stage.SCRIPT)
    assert updated.stage == Stage.AUDIO
    assert ("audio", job.id) in tasks.calls


@pytest.mark.asyncio
async def test_cancel_enqueues_cleanup(pipeline):
    svc, _, tasks = pipeline
    job = await svc.start_job(chat_id=1, user_id=42, prompt="Create a video about space")
    await svc.cancel(job.id)
    assert ("cleanup", job.id) in tasks.calls
