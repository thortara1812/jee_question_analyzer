"""Bounded transient retries. Provider messages never reach UI or logs."""
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import URLError


class ServiceError(RuntimeError):
    """Sanitized failure safe to present to students."""

    def __init__(self, message: str, code: str = "workflow_failed"):
        super().__init__(message)
        self.code = code


PUBLIC_FAILURES = {
    "authentication": "The model provider rejected the backend credentials. Check GROQ_API_KEY on Render.",
    "rate_limit": "The model provider's rate limit was reached. Wait before retrying.",
    "transient": "The model provider timed out or is temporarily unavailable. Please retry later.",
    "invalid_request": "The model provider rejected the backend request. Check the configured model and backend logs.",
    "provider_compatibility": "The model request contains unsupported provider metadata. Deploy the latest backend compatibility fix.",
    "invalid_output": "The model returned an invalid structured answer. Please retry.",
    "workflow_failed": "The backend workflow could not complete. Check backend logs or retry later.",
}


def category(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__.lower()
    if (status == 400 or "badrequest" in name) and "cache_breakpoint" in str(exc):
        return "provider_compatibility"
    if status == 429 or "ratelimit" in name:
        return "rate_limit"
    if (status in (408, 500, 502, 503, 504) or "timeout" in name or "connection" in name
            or status is None and isinstance(exc, URLError)):
        return "transient"
    if status in (401, 403) or "authentication" in name:
        return "authentication"
    return "invalid_request"


def retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        try:
            return max(0.0, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None


def retry_call(call, *, attempts=3, sleep=time.sleep, metrics=None, stage="request"):
    for attempt in range(attempts):
        started = time.monotonic()
        try:
            result = call()
            if metrics is not None:
                metrics.append({"stage": stage, "attempt": attempt + 1,
                                "seconds": time.monotonic() - started, "status": "ok"})
            return result
        except Exception as exc:
            kind = category(exc)
            if metrics is not None:
                metrics.append({"stage": stage, "attempt": attempt + 1,
                                "seconds": time.monotonic() - started, "status": kind})
            if kind not in ("rate_limit", "transient") or attempt + 1 == attempts:
                raise ServiceError(f"Service request failed ({kind}). Please check configuration or retry later.", code=kind) from None
            delay = retry_after(exc)
            if delay is not None and delay > 60:
                raise ServiceError("Provider requests a longer cooldown. Please retry later.", code=kind) from None
            sleep(delay if delay is not None else 2 ** attempt + random.random())
