"""One bounded worker for agent jobs; no expensive work in HTTP request handlers."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock
import hashlib
import logging
import multiprocessing
import time
from uuid import uuid4

from .api_contracts import JobRequest, JobSnapshot
from .reliability import PUBLIC_FAILURES, ServiceError
from .schemas import Result

logger = logging.getLogger("agentic_jee_system.jobs")


class QueueFull(Exception):
    pass


class RequestConflict(Exception):
    pass


def _isolated_work(runner, payload, sender):
    """Child process sends only a validated result or an allowlisted error code."""
    try:
        result = Result.model_validate(runner(payload.question, payload.mode, payload.subject))
        sender.send({"result": result.model_dump(mode="json")})
    except Exception as exc:
        code = exc.code if isinstance(exc, ServiceError) and exc.code in PUBLIC_FAILURES else "workflow_failed"
        # Render needs enough information to diagnose runtime failures, but provider
        # messages and question text may contain sensitive data and are never logged.
        logger.error("isolated job failed: code=%s exception_type=%s", code, type(exc).__name__)
        sender.send({"error_code": code})
    finally:
        sender.close()


class JobManager:
    def __init__(self, runner, capacity: int = 3, retention: int = 100, ttl: int = 1800,
                 isolated: bool = False, job_timeout: float = 300, min_interval: float = 0):
        self.runner = runner
        self.retention = retention
        self.ttl = ttl
        self.jobs = {}
        self.finished = {}
        self.requests = {}
        self.job_keys = {}
        self.isolated = isolated
        self.job_timeout = job_timeout
        self.min_interval = min_interval
        self.next_start = 0
        self.active_process = None
        self.stopping = Event()
        self.lock = Lock()
        self.slots = BoundedSemaphore(capacity)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jee-worker")

    def _forget(self, job_id):
        self.finished.pop(job_id, None)
        self.jobs.pop(job_id, None)
        key = self.job_keys.pop(job_id, None)
        if key is not None:
            self.requests.pop(key, None)

    def _prune(self, make_room=False):
        now = time.monotonic()
        expired = [key for key, finished in self.finished.items() if now - finished > self.ttl]
        for key in expired:
            self._forget(key)
        while make_room and len(self.jobs) >= self.retention and self.finished:
            oldest = next(iter(self.finished))
            self._forget(oldest)

    def submit(self, request: JobRequest, request_key=None) -> JobSnapshot:
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        job_id = uuid4()
        with self.lock:
            self._prune(make_room=True)
            existing = self.requests.get(request_key) if request_key is not None else None
            if existing:
                previous_fingerprint, previous_id = existing
                if previous_fingerprint != fingerprint:
                    raise RequestConflict
                return self.jobs[previous_id].model_copy(deep=True)
            if self.stopping.is_set() or not self.slots.acquire(blocking=False):
                raise QueueFull
            self.jobs[job_id] = JobSnapshot(job_id=job_id, status="queued")
            if request_key is not None:
                self.requests[request_key] = (fingerprint, job_id)
                self.job_keys[job_id] = request_key
        try:
            self.executor.submit(self._execute, job_id, request)
        except Exception:
            with self.lock:
                self._forget(job_id)
            self.slots.release()
            raise
        return self.get(job_id)

    def _execute(self, job_id, request):
        try:
            if self.stopping.wait(max(0, self.next_start - time.monotonic())):
                raise ServiceError("Backend is stopping.")
            with self.lock:
                self.jobs[job_id].status = "running"
            result = (self._run_isolated(request) if self.isolated else
                      Result.model_validate(self.runner(request.question, request.mode, request.subject)))
            with self.lock:
                self.jobs[job_id].result = result
                self.jobs[job_id].status = "completed"
        except Exception as exc:
            # Never return provider exceptions, tracebacks or request data.
            code = exc.code if isinstance(exc, ServiceError) and exc.code in PUBLIC_FAILURES else "workflow_failed"
            logger.error("job failed: job_id=%s code=%s exception_type=%s", job_id, code, type(exc).__name__)
            with self.lock:
                self.jobs[job_id].error = PUBLIC_FAILURES[code]
                self.jobs[job_id].error_code = code
                self.jobs[job_id].status = "failed"
        finally:
            with self.lock:
                self.finished[job_id] = time.monotonic()
            self.next_start = time.monotonic() + self.min_interval
            self.slots.release()

    def _run_isolated(self, request):
        """A real process can be stopped at the deadline; a Python thread cannot."""
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_isolated_work, args=(self.runner, request, sender), daemon=True)
        try:
            process.start()
            sender.close()
            with self.lock:
                self.active_process = process
            if not receiver.poll(self.job_timeout):
                raise ServiceError("Question exceeded the execution deadline.", code="job_timeout")
            try:
                payload = receiver.recv()
            except EOFError:
                logger.error("isolated worker exited without a result: exit_code=%s", process.exitcode)
                raise ServiceError("Backend worker stopped before producing a result.") from None
            if "error_code" in payload:
                code = payload["error_code"]
                raise ServiceError(PUBLIC_FAILURES.get(code, PUBLIC_FAILURES["workflow_failed"]), code=code)
            return Result.model_validate(payload["result"])
        finally:
            sender.close()
            receiver.close()
            if process.pid is not None:
                process.join(timeout=.5)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
            with self.lock:
                self.active_process = None

    def stats(self):
        with self.lock:
            return {"running": sum(job.status == "running" for job in self.jobs.values()),
                    "queued": sum(job.status == "queued" for job in self.jobs.values())}

    def get(self, job_id) -> JobSnapshot | None:
        with self.lock:
            self._prune()
            job = self.jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def close(self):
        self.stopping.set()
        with self.lock:
            process = self.active_process
        if process is not None and process.is_alive():
            process.terminate()
        self.executor.shutdown(wait=False, cancel_futures=True)
