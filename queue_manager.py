"""Testable local download queue state management."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Literal

from downloader import DownloadRequest


JobState = Literal["queued", "downloading", "cancelling", "completed", "cancelled", "failed"]
FINAL_STATES = frozenset({"completed", "cancelled", "failed"})


class DuplicateJobError(ValueError):
    """The same request is already active in the queue."""


@dataclass(frozen=True)
class QueueCounts:
    """Atomic snapshot of the queue counters."""
    total: int
    active: int
    finished: int


def request_identity(request: DownloadRequest) -> tuple[str, str, str, int]:
    """Stable identity key without persisting history outside the process."""

    destination = os.path.normcase(os.path.abspath(request.destination))
    selected_quality = request.audio_bitrate if request.output_type == "audio" else request.quality
    return (request.url, request.output_type, destination, selected_quality)


@dataclass
class QueueJob:
    job_id: int
    title: str
    request: DownloadRequest
    cancel_event: threading.Event = field(default_factory=threading.Event)
    state: JobState = "queued"


class QueueManager:
    """Coordinates state transitions and duplicate detection without depending on the UI."""

    def __init__(self) -> None:
        self._jobs: dict[int, QueueJob] = {}
        self._active_identities: set[tuple[str, str, str, int]] = set()
        self._next_job_id = 1
        self._lock = threading.Lock()

    def create(self, title: str, request: DownloadRequest) -> QueueJob:
        identity = request_identity(request)
        with self._lock:
            if identity in self._active_identities:
                raise DuplicateJobError("Esta descarga ya está en la cola.")
            job = QueueJob(self._next_job_id, title, request)
            self._next_job_id += 1
            self._jobs[job.job_id] = job
            self._active_identities.add(identity)
            return job

    def get(self, job_id: int) -> QueueJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.state != "queued" or job.cancel_event.is_set():
                if job and job.state not in FINAL_STATES:
                    self._finish_locked(job, "cancelled")
                return False
            job.state = "downloading"
            return True

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.state in FINAL_STATES:
                return False
            job.cancel_event.set()
            job.state = "cancelling"
            return True

    def finish(self, job_id: int, state: Literal["completed", "cancelled", "failed"]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.state not in FINAL_STATES:
                self._finish_locked(job, state)

    def cancel_all(self) -> int:
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.state not in FINAL_STATES]
            for job in jobs:
                job.cancel_event.set()
                job.state = "cancelling"
            return len(jobs)

    def counts(self) -> QueueCounts:
        """Return total, active, and finished counts in a single lock acquisition."""
        with self._lock:
            jobs = list(self._jobs.values())
        finished = sum(j.state in FINAL_STATES for j in jobs)
        return QueueCounts(
            total=len(jobs),
            active=len(jobs) - finished,
            finished=finished,
        )

    @property
    def active_count(self) -> int:
        return self.counts().active

    @property
    def finished_count(self) -> int:
        return self.counts().finished

    @property
    def total_count(self) -> int:
        return self.counts().total

    def remove_finished(self) -> tuple[int, ...]:
        with self._lock:
            identifiers = tuple(
                job_id for job_id, job in self._jobs.items() if job.state in FINAL_STATES
            )
            for job_id in identifiers:
                del self._jobs[job_id]
            return identifiers

    def _finish_locked(
        self, job: QueueJob, state: Literal["completed", "cancelled", "failed"]
    ) -> None:
        job.state = state
        self._active_identities.discard(request_identity(job.request))
