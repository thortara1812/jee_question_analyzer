"""Server-to-server Streamlit integration; never retry an uncertain job submission."""
import os
import hashlib
import math
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import ValidationError

from .api_contracts import JobRequest, JobSnapshot
from .reliability import PUBLIC_FAILURES, ServiceError
from .schemas import Result


def transcribe_remote(data: bytes) -> str:
    from .vision import normalize_image
    encoded = normalize_image(data)
    url, token = backend_settings()
    try:
        with httpx.Client(timeout=120) as client:
            response = client.post(url + "/api/v1/transcribe",
                headers={"Authorization": "Bearer " + token}, json={"image_base64": encoded})
            if response.status_code == 404:
                raise ServiceError("Deploy the latest Render backend to enable image upload.")
            if response.status_code == 502:
                detail = response.json().get("detail", {})
                code = detail.get("code") if isinstance(detail, dict) else None
                raise ServiceError(PUBLIC_FAILURES.get(code, PUBLIC_FAILURES["workflow_failed"]))
            result = _response(response)
            text = result.get("text")
            if not isinstance(text, str) or not 3 <= len(text) <= 4000:
                raise ServiceError("The backend returned an invalid image transcription.")
            return text
    except httpx.RequestError:
        raise ServiceError("Image extraction could not connect to the backend. Retry when Render is live.") from None


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
        try:
            detail = response.json().get("detail", {})
        except (ValueError, AttributeError):
            detail = {}
        if isinstance(detail, dict) and detail.get("code") == "queue_full":
            running, queued = detail.get("running"), detail.get("queued")
            if type(running) is int and type(queued) is int and 0 <= running <= 3 and 0 <= queued <= 3:
                raise ServiceError(f"The server has {running} question(s) running and {queued} waiting. Wait about 20 seconds before retrying.", code="queue_full")
        raise ServiceError("The backend is temporarily busy or limiting requests. Wait before retrying.", code="rate_limit")
    if response.status_code == 404:
        raise ServiceError("The backend job was not found. It may have expired or the server restarted. You can submit it again.", code="job_not_found")
    if response.status_code >= 400:
        raise ServiceError("The backend is unavailable or not configured. Check its deployment logs.")
    if "application/json" not in response.headers.get("content-type", ""):
        raise ServiceError("The Render URL is serving a webpage instead of the backend API. Change its start command to api_server.py.")
    try:
        return response.json()
    except ValueError:
        raise ServiceError("The backend returned an invalid response.") from None


def run_remote(question: str, mode="solve", subject="Auto", *, client=None, sleep=time.sleep,
               clock=time.monotonic, wait_seconds=600, poll_seconds=2, state=None) -> Result:
    request = JobRequest(question=question, mode=mode, subject=subject)
    state = {} if state is None else state
    fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    if state.get("fingerprint") != fingerprint or not state.get("request_key"):
        state.clear()
        state.update(fingerprint=fingerprint, request_key=str(uuid4()))
    request_key = state["request_key"]
    previous_job = state.get("job_id")
    uncertain = state.get("submission_uncertain")

    def owns_state():
        # An older Streamlit script may finish after a new question was submitted.
        return state.get("fingerprint") == fingerprint and state.get("request_key") == request_key

    def clear_state():
        if owns_state():
            state.clear()
    url, token = backend_settings()
    owned_client = client is None
    client = client or httpx.Client(base_url=url + "/", headers={"Authorization": "Bearer " + token},
                                  timeout=httpx.Timeout(60, connect=10), follow_redirects=False)
    try:
        # /health distinguishes the API from Streamlit's catch-all HTML routes.
        health = _response(client.get("health"))
        if health.get("service") != "agentic-jee-api":
            raise ServiceError("JEE_API_URL does not point to the Agentic JEE backend API.")
        if previous_job:
            snapshot = JobSnapshot.model_validate(_response(client.get(f"api/v1/jobs/{previous_job}")))
        else:
            if uncertain and not health.get("idempotency_supported"):
                raise ServiceError("A previous submission may still be running. Update the backend before safely retrying it.")
            if owns_state():
                state["submission_uncertain"] = True
            response = client.post("api/v1/jobs", json=request.model_dump(),
                                   headers={"Idempotency-Key": request_key})
            if owns_state() and response.status_code in (401, 403, 429):
                state.pop("submission_uncertain", None)
            snapshot = JobSnapshot.model_validate(_response(response))
            if owns_state():
                state["job_id"] = str(snapshot.job_id)
                state.pop("submission_uncertain", None)
        deadline = clock() + wait_seconds
        while True:
            if snapshot.status == "completed":
                if snapshot.result is None:
                    raise ServiceError("The backend completed without a valid result.")
                clear_state()
                return snapshot.result
            if snapshot.status == "failed":
                # Only show locally allowlisted messages, never arbitrary server errors.
                message = PUBLIC_FAILURES.get(snapshot.error_code, PUBLIC_FAILURES["workflow_failed"])
                if snapshot.error_code == "rate_limit" and snapshot.retry_after_seconds is not None:
                    message += f" Groq requested a cooldown of {math.ceil(snapshot.retry_after_seconds)} seconds when this job failed; allow that time before retrying."
                clear_state()
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
    except ServiceError as exc:
        if exc.code == "job_not_found":
            clear_state()
        raise
    finally:
        if owned_client:
            client.close()
