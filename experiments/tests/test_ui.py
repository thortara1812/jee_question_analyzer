"""Streamlit rerun regression checks with the provider mocked."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from agentic_jee_system.schemas import Result

APP = str(Path(__file__).resolve().parents[2] / "app.py")


class UITests(unittest.TestCase):
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
