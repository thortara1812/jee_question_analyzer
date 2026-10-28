"""Authenticated backend API. Run one process because jobs are in memory."""
from contextlib import asynccontextmanager
import hmac
import os
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .api_contracts import JobRequest, JobSnapshot
from .api_jobs import JobManager, QueueFull
from .workflow import run

bearer = HTTPBearer(auto_error=False)


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    expected = os.getenv("JEE_API_TOKEN", "").strip()
    if not expected or expected == "replace_with_a_long_random_shared_token":
        raise HTTPException(503, "Configure JEE_API_TOKEN on the Render backend.")
    if (credentials is None or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(credentials.credentials.encode(), expected.encode())):
        raise HTTPException(401, "Backend authorization failed.", headers={"WWW-Authenticate": "Bearer"})


def create_app(runner=run) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        load_dotenv()
        application.state.jobs = JobManager(runner)
        yield
        application.state.jobs.close()

    application = FastAPI(title="Agentic JEE Backend", version="1.0.0", lifespan=lifespan)

    @application.get("/health")
    def health():
        token = os.getenv("JEE_API_TOKEN", "").strip()
        return {"status": "ok", "service": "agentic-jee-api", "api_version": "1",
                "configured": bool(token and token != "replace_with_a_long_random_shared_token")}

    @application.post("/api/v1/jobs", response_model=JobSnapshot, status_code=202, dependencies=[Depends(authorize)])
    def submit(payload: JobRequest, request: Request):
        try:
            return request.app.state.jobs.submit(payload)
        except QueueFull:
            raise HTTPException(429, "The backend is busy. Wait before submitting another question.",
                                headers={"Retry-After": "20"}) from None

    @application.get("/api/v1/jobs/{job_id}", response_model=JobSnapshot, dependencies=[Depends(authorize)])
    def status(job_id: UUID, request: Request):
        job = request.app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found or expired. A backend restart also clears jobs.")
        return job

    return application


app = create_app()
