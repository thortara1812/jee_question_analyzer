"""Backend/client integration without provider calls or external networking."""
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from agentic_jee_system.api import create_app
from agentic_jee_system.api_client import run_remote
from agentic_jee_system.schemas import Result
from agentic_jee_system.reliability import ServiceError

ENV = {"JEE_API_TOKEN": "test-shared-token", "JEE_API_URL": "https://backend.example"}
AUTH = {"Authorization": "Bearer test-shared-token"}
PAYLOAD = {"question": "Solve 2x + 5 = 15.", "mode": "solve", "subject": "Mathematics"}


class APITests(unittest.TestCase):
    def test_end_to_end_client_receives_validated_result(self):
        expected = Result(mode="solve", status="verified", markdown="x = 5")
        runner = Mock(return_value=expected)
        with patch.dict("os.environ", ENV), TestClient(create_app(runner), headers=AUTH) as client:
            result = run_remote(**PAYLOAD, client=client, sleep=lambda _: time.sleep(.005), wait_seconds=2)
        self.assertEqual(result, expected)
        runner.assert_called_once_with(PAYLOAD["question"], "solve", "Mathematics")

    def test_health_is_public_and_missing_auth_cannot_start_job(self):
        runner = Mock()
        with patch.dict("os.environ", ENV), TestClient(create_app(runner)) as client:
            self.assertEqual(client.get("/health").json()["service"], "agentic-jee-api")
            self.assertEqual(client.post("/api/v1/jobs", json=PAYLOAD).status_code, 401)
            self.assertEqual(client.get(f"/api/v1/jobs/{uuid4()}").status_code, 401)
        runner.assert_not_called()

    def test_missing_backend_token_fails_closed(self):
        with patch.dict("os.environ", {"JEE_API_TOKEN": ""}), TestClient(create_app(Mock())) as client:
            self.assertEqual(client.post("/api/v1/jobs", json=PAYLOAD, headers=AUTH).status_code, 503)

    def test_invalid_input_and_unknown_jobs(self):
        with patch.dict("os.environ", ENV), TestClient(create_app(Mock()), headers=AUTH) as client:
            self.assertEqual(client.post("/api/v1/jobs", json={**PAYLOAD, "question": "   "}).status_code, 422)
            self.assertEqual(client.post("/api/v1/jobs", json={**PAYLOAD, "mode": "other"}).status_code, 422)
            self.assertEqual(client.get(f"/api/v1/jobs/{uuid4()}").status_code, 404)

    def test_queue_is_bounded(self):
        release = threading.Event()
        def blocked(*_):
            release.wait(3)
            return Result(mode="solve", status="needs_review", markdown="Review")
        with patch.dict("os.environ", ENV), TestClient(create_app(blocked), headers=AUTH) as client:
            try:
                for _ in range(3):
                    self.assertEqual(client.post("/api/v1/jobs", json=PAYLOAD).status_code, 202)
                full = client.post("/api/v1/jobs", json=PAYLOAD)
                self.assertEqual(full.status_code, 429)
                self.assertEqual(full.headers["retry-after"], "20")
            finally:
                release.set()

    def test_backend_exception_does_not_leak_provider_details(self):
        def failed(*_):
            raise RuntimeError("SECRET_PROVIDER_DATA")
        with patch.dict("os.environ", ENV), TestClient(create_app(failed), headers=AUTH) as client:
            with self.assertRaises(ServiceError) as ctx:
                run_remote(**PAYLOAD, client=client, sleep=lambda _: time.sleep(.005), wait_seconds=2)
            self.assertNotIn("SECRET_PROVIDER_DATA", str(ctx.exception))


class APIClientTests(unittest.TestCase):
    def test_html_streamlit_page_is_not_accepted_as_api(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, text="<html>Streamlit</html>", headers={"content-type": "text/html"}))
        with patch.dict("os.environ", ENV), httpx.Client(base_url="https://backend.example/", transport=transport) as client:
            with self.assertRaisesRegex(ServiceError, "webpage instead"):
                run_remote(**PAYLOAD, client=client)

    def test_uncertain_post_is_never_automatically_retried(self):
        posts = []
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"service": "agentic-jee-api"})
            posts.append(request)
            raise httpx.ReadTimeout("timeout", request=request)
        with patch.dict("os.environ", ENV), httpx.Client(base_url="https://backend.example/", transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ServiceError, "timed out"):
                run_remote(**PAYLOAD, client=client)
        self.assertEqual(len(posts), 1)

    def test_invalid_result_is_rejected(self):
        def handler(request):
            if request.url.path == "/health":
                return httpx.Response(200, json={"service": "agentic-jee-api"})
            return httpx.Response(202, json={"job_id": str(uuid4()), "status": "completed", "result": {"fake": "answer"}})
        with patch.dict("os.environ", ENV), httpx.Client(base_url="https://backend.example/", transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ServiceError, "contract"):
                run_remote(**PAYLOAD, client=client)

    def test_polling_stops_after_wait_budget(self):
        job = {"job_id": str(uuid4()), "status": "queued"}
        def handler(request):
            return httpx.Response(200 if request.method == "GET" else 202,
                json={"service": "agentic-jee-api"} if request.url.path == "/health" else job)
        with patch.dict("os.environ", ENV), httpx.Client(base_url="https://backend.example/", transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ServiceError, "still processing"):
                run_remote(**PAYLOAD, client=client, clock=Mock(side_effect=[0, 10]), wait_seconds=1)

    def test_insecure_remote_url_is_rejected(self):
        with patch.dict("os.environ", {**ENV, "JEE_API_URL": "http://remote.example"}):
            with self.assertRaisesRegex(ServiceError, "HTTPS"):
                run_remote(**PAYLOAD)
