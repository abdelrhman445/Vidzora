from __future__ import annotations


class DomainError(Exception):
    """Base domain exception."""


class ActiveJobExistsError(DomainError):
    def __init__(self, job_id: str, stage: str, status: str) -> None:
        super().__init__(
            f"You already have an active job ({status} / {stage}). "
            "Use the approval buttons or /cancel first."
        )
        self.job_id = job_id


class JobNotFoundError(DomainError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job not found: {job_id}")
        self.job_id = job_id


class InvalidJobTransitionError(DomainError):
    def __init__(self, job_id: str, current: str, expected: str) -> None:
        super().__init__(
            f"Job {job_id} cannot proceed from '{current}' (expected '{expected}')"
        )
        self.job_id = job_id


class ExternalServiceError(DomainError):
    pass
