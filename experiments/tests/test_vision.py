"""Image boundaries and extraction transport, without external model calls."""
import base64
import io
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from fastapi.testclient import TestClient
from agentic_jee_system.api import create_app
from agentic_jee_system.vision import normalize_image, transcribe_image
from agentic_jee_system.reliability import ServiceError

def sample_image():
    output = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(output, "PNG")
    return output.getvalue()

class VisionTests(unittest.TestCase):
    def test_image_reencoding_and_validation(self):
        encoded = normalize_image(sample_image())
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            self.assertEqual(image.format, "JPEG")
        for invalid in (b"not an image", b"x" * (3 * 1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                normalize_image(invalid)

    def test_provider_extraction_and_errors_are_sanitized(self):
        client = Mock()
        client.post.return_value.status_code = 200
        client.post.return_value.json.return_value = {"choices": [{"message": {"content": "Solve 2x + 5 = 15."}}]}
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            self.assertEqual(transcribe_image(normalize_image(sample_image()), client=client), "Solve 2x + 5 = 15.")
            client.post.return_value.status_code = 429
            with self.assertRaises(ServiceError) as ctx:
                transcribe_image(normalize_image(sample_image()), client=client)
            self.assertEqual(ctx.exception.code, "rate_limit")

    def test_endpoint_authentication_and_extraction(self):
        with patch.dict("os.environ", {"JEE_API_TOKEN": "test-token"}), patch("agentic_jee_system.api.transcribe_image", return_value="Solve 2x = 10.") as extract:
            with TestClient(create_app(lambda *_: None)) as client:
                payload = {"image_base64": normalize_image(sample_image())}
                self.assertEqual(client.post("/api/v1/transcribe", json=payload).status_code, 401)
                response = client.post("/api/v1/transcribe", json=payload, headers={"Authorization": "Bearer test-token"})
                self.assertEqual(response.json(), {"text": "Solve 2x = 10."})
                extract.assert_called_once()
