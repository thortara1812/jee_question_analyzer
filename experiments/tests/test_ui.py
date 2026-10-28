"""Streamlit rerun regression checks with the provider mocked."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from agentic_jee_system.schemas import Result

APP = str(Path(__file__).resolve().parents[2] / "app.py")


class UITests(unittest.TestCase):
    def test_configured_frontend_calls_api_instead_of_local_agents(self):
        result = Result(mode="solve", status="verified", markdown="Remote answer")
        with patch.dict("os.environ", {"JEE_API_URL": "https://backend.example"}), patch("agentic_jee_system.api_client.run_remote", return_value=result) as remote, patch("agentic_jee_system.workflow.run") as local:
            app = AppTest.from_file(APP, default_timeout=30).run()
            app.text_area[0].set_value("Solve a question").run()
            next(button for button in app.button if button.label == "Run / retry").click().run()
            self.assertEqual(len(app.exception), 0)
            remote.assert_called_once()
            local.assert_not_called()

    def test_cloud_history_does_not_read_shared_sqlite(self):
        with patch.dict("os.environ", {"JEE_HISTORY_MODE": "session"}), patch("agentic_jee_system.history.recent") as shared:
            app = AppTest.from_file(APP, default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            shared.assert_not_called()

    def test_session_history_does_not_leak_to_another_browser(self):
        result = Result(mode="solve", status="needs_review", markdown="Private session example.")
        with patch.dict("os.environ", {"JEE_HISTORY_MODE": "session"}), patch("agentic_jee_system.workflow.run", return_value=result), patch("agentic_jee_system.history.save") as disk:
            first = AppTest.from_file(APP, default_timeout=30).run()
            first.checkbox[0].check().run()
            first.text_area[0].set_value("Private question").run()
            next(button for button in first.button if button.label == "Run / retry").click().run()
            self.assertEqual(len(first.session_state.request_history), 1)
            second = AppTest.from_file(APP, default_timeout=30).run()
            self.assertEqual(second.session_state.request_history, [])
            disk.assert_not_called()

    def test_example_callback_and_empty_submission(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        next(button for button in app.button if button.label == "Physics example").click().run()
        self.assertIn("2 kg", app.text_area[0].value)
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value("").run()
        next(button for button in app.button if button.label == "Run / retry").click().run()
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.exception), 0)

    def test_rerun_does_not_replay_expensive_request(self):
        result = Result(mode="solve", status="needs_review", markdown="Clarify the question.")
        with patch("agentic_jee_system.workflow.run", return_value=result) as request:
            app = AppTest.from_file(APP, default_timeout=30).run()
            app.text_area[0].set_value("A question").run()
            next(button for button in app.button if button.label == "Run / retry").click().run()
            app.run()
            self.assertEqual(request.call_count, 1)
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Clarify the question.", [element.value for element in app.markdown])


if __name__ == "__main__":
    unittest.main()
