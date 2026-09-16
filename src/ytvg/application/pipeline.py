from __future__ import annotations

from ytvg.application.ports import JobRepository, TaskDispatcher, WorkspaceManager
from ytvg.domain.entities import VideoJob
from ytvg.domain.enums import JobStatus, Stage
from ytvg.domain.exceptions import ActiveJobExistsError, InvalidJobTransitionError, JobNotFoundError

_STAGE_ORDER = (Stage.SCRIPT, Stage.AUDIO, Stage.IMAGES, Stage.VIDEO)


class PipelineService:
    """Application service coordinating approval-gated stage transitions."""

    def __init__(
        self,
        jobs: JobRepository,
        tasks: TaskDispatcher,
        workspace: WorkspaceManager,
    ) -> None:
        self._jobs = jobs
        self._tasks = tasks
        self._workspace = workspace

    async def start_job(self, *, chat_id: int, user_id: int, prompt: str) -> VideoJob:
        existing = await self._jobs.find_active_for_user(user_id)
        if existing:
            raise ActiveJobExistsError(existing.id, existing.stage.value, existing.status.value)

        job = VideoJob(chat_id=chat_id, user_id=user_id, prompt=prompt.strip())
        job.workspace_dir = self._workspace.prepare(job.id)
        job.mark_processing(Stage.SCRIPT)
        await self._jobs.create(job)
        self._tasks.enqueue_script(job.id)
        return job

    async def approve(self, job_id: str, expected_stage: Stage) -> VideoJob:
        job = await self._require(job_id)
        self._assert_awaiting(job, expected_stage)

        nxt = self._next_stage(expected_stage)
        if nxt is None:
            job.mark_completed()
            await self._jobs.save(job)
            self._tasks.enqueue_cleanup(job.id)
            return job

        job.mark_processing(nxt)
        await self._jobs.save(job)
        self._dispatch(nxt, job.id)
        return job

    async def regenerate(self, job_id: str, stage: Stage) -> VideoJob:
        job = await self._require(job_id)
        self._assert_awaiting(job, stage)
        job.mark_processing(stage)
        await self._jobs.save(job)
        self._dispatch(stage, job.id)
        return job

    async def cancel(self, job_id: str) -> VideoJob:
        job = await self._require(job_id)
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}:
            return job
        job.mark_cancelled()
        await self._jobs.save(job)
        self._tasks.enqueue_cleanup(job.id)
        return job

    async def get_job(self, job_id: str) -> VideoJob | None:
        return await self._jobs.get(job_id)

    def enqueue_cleanup(self, job_id: str) -> None:
        self._tasks.enqueue_cleanup(job_id)

    def _dispatch(self, stage: Stage, job_id: str) -> None:
        if stage == Stage.SCRIPT:
            self._tasks.enqueue_script(job_id)
        elif stage == Stage.AUDIO:
            self._tasks.enqueue_audio(job_id)
        elif stage == Stage.IMAGES:
            self._tasks.enqueue_images(job_id)
        elif stage == Stage.VIDEO:
            self._tasks.enqueue_video(job_id)

    async def _require(self, job_id: str) -> VideoJob:
        job = await self._jobs.get(job_id)
        if not job:
            raise JobNotFoundError(job_id)
        return job

    @staticmethod
    def _assert_awaiting(job: VideoJob, expected: Stage) -> None:
        if job.status != JobStatus.AWAITING_APPROVAL or job.stage != expected:
            raise InvalidJobTransitionError(
                job.id, f"{job.status}:{job.stage}", f"awaiting_approval:{expected}"
            )

    @staticmethod
    def _next_stage(stage: Stage) -> Stage | None:
        order = list(_STAGE_ORDER)
        idx = order.index(stage)
        if idx + 1 >= len(order):
            return None
        return order[idx + 1]
