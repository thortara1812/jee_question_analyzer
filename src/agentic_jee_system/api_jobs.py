"""One bounded worker for agent jobs; no expensive work in HTTP request handlers."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import time
from uuid import uuid4

from .api_contracts import JobRequest, JobSnapshot
from .reliability import PUBLIC_FAILURES, ServiceError
from .schemas import Result


class QueueFull(Exception):
    pass


class JobManager:
    def __init__(self, runner, capacity: int = 3, retention: int = 100, ttl: int = 1800):
        self.runner = runner
        self.retention = retention
        self.ttl = ttl
        self.jobs = {}
        self.finished = {}
        self.lock = Lock()
        self.slots = BoundedSemaphore(capacity)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jee-worker")

    def _prune(self, make_room=False):
        now = time.monotonic()
        expired = [key for key, finished in self.finished.items() if now - finished > self.ttl]
        for key in expired:
            self.finished.pop(key, None)
            self.jobs.pop(key, None)
        while make_room and len(self.jobs) >= self.retention and self.finished:
            oldest = next(iter(self.finished))
            self.finished.pop(oldest)
            self.jobs.pop(oldest, None)

    def submit(self, request: JobRequest) -> JobSnapshot:
        if not self.slots.acquire(blocking=False):
            raise QueueFull
        job_id = uuid4()
        try:
            with self.lock:
                self._prune(make_room=True)
                self.jobs[job_id] = JobSnapshot(job_id=job_id, status="queued")
            self.executor.submit(self._execute, job_id, request)
        except Exception:
            with self.lock:
                self.jobs.pop(job_id, None)
            self.slots.release()
            raise
        return self.get(job_id)

    def _execute(self, job_id, request):
        with self.lock:
            self.jobs[job_id].status = "running"
        try:
            result = Result.model_validate(self.runner(request.question, request.mode, request.subject))
            with self.lock:
                self.jobs[job_id].result = result
                self.jobs[job_id].status = "completed"
        except Exception as exc:
            # Never return provider exceptions, tracebacks or request data.
            code = exc.code if isinstance(exc, ServiceError) and exc.code in PUBLIC_FAILURES else "workflow_failed"
            with self.lock:
                self.jobs[job_id].error = PUBLIC_FAILURES[code]
                self.jobs[job_id].error_code = code
                self.jobs[job_id].status = "failed"
        finally:
            with self.lock:
                self.finished[job_id] = time.monotonic()
            self.slots.release()

    def get(self, job_id) -> JobSnapshot | None:
        with self.lock:
            self._prune()
            job = self.jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
