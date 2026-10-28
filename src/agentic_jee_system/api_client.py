"""Server-to-server Streamlit integration; never retry an uncertain job submission."""
import os
import time
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from .api_contracts import JobRequest, JobSnapshot
from .reliability import PUBLIC_FAILURES, ServiceError
from .schemas import Result


def backend_settings():
    url = os.getenv("JEE_API_URL", "").strip().rstrip("/")
    token = os.getenv("JEE_API_TOKEN", "").strip()
    parsed = urlsplit(url)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.scheme != "https" and not (parsed.scheme == "http" and local)):
        raise ServiceError("Set JEE_API_URL to the HTTPS backend address (HTTP is allowed only for local testing).")
    if not token or token == "replace_with_a_long_random_shared_token":
        raise ServiceError("Set JEE_API_TOKEN in Streamlit Secrets to match the Render backend token.")
    return url, token


def _response(response: httpx.Response):
    if response.status_code in (401, 403):
        raise ServiceError("Backend authorization failed. Check JEE_API_TOKEN on both hosts.")
    if response.status_code == 429:
        raise ServiceError("The backend queue is full. Wait before submitting another question.")
    if response.status_code == 404:
        raise ServiceError("The backend job was not found. It may have expired or the server restarted.")
    if response.status_code >= 400:
        raise ServiceError("The backend is unavailable or not configured. Check its deployment logs.")
    if "application/json" not in response.headers.get("content-type", ""):
        raise ServiceError("The Render URL is serving a webpage instead of the backend API. Change its start command to api_server.py.")
    try:
        return response.json()
    except ValueError:
        raise ServiceError("The backend returned an invalid response.") from None


def run_remote(question: str, mode="solve", subject="Auto", *, client=None, sleep=time.sleep,
               clock=time.monotonic, wait_seconds=600, poll_seconds=2) -> Result:
    request = JobRequest(question=question, mode=mode, subject=subject)
    url, token = backend_settings()
    owned_client = client is None
    client = client or httpx.Client(base_url=url + "/", headers={"Authorization": "Bearer " + token},
                                  timeout=httpx.Timeout(60, connect=10), follow_redirects=False)
    try:
        # /health distinguishes the API from Streamlit's catch-all HTML routes.
        health = _response(client.get("health"))
        if health.get("service") != "agentic-jee-api":
            raise ServiceError("JEE_API_URL does not point to the Agentic JEE backend API.")
        snapshot = JobSnapshot.model_validate(_response(client.post("api/v1/jobs", json=request.model_dump())))
        deadline = clock() + wait_seconds
        while True:
            if snapshot.status == "completed":
                if snapshot.result is None:
                    raise ServiceError("The backend completed without a valid result.")
                return snapshot.result
            if snapshot.status == "failed":
                # Only show locally allowlisted messages, never arbitrary server errors.
                message = PUBLIC_FAILURES.get(snapshot.error_code, PUBLIC_FAILURES["workflow_failed"])
                raise ServiceError(message, code=snapshot.error_code or "workflow_failed")
            if clock() >= deadline:
                raise ServiceError("The backend is still processing. A job may remain active; avoid immediately submitting it again.")
            sleep(poll_seconds)
            snapshot = JobSnapshot.model_validate(_response(client.get(f"api/v1/jobs/{snapshot.job_id}")))
    except httpx.TimeoutException:
        raise ServiceError("The backend request timed out. Render may be starting up; an accepted job can continue running. Avoid immediate duplicate submissions.") from None
    except httpx.RequestError:
        raise ServiceError("Could not connect to the backend. Check that the Render service is live.") from None
    except (ValidationError, ValueError, AttributeError):
        raise ServiceError("The backend returned data that does not match the application contract.") from None
    finally:
        if owned_client:
            client.close()
