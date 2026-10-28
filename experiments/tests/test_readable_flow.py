import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from agentic_jee_system.backend import CrewBackend, Settings
from agentic_jee_system.workflow import run

class ReadableFlowTests(unittest.TestCase):
    def test_production_path_accepts_plain_text_without_schema_submission(self):
        backend = Mock(spec=CrewBackend)
        backend.tool_calls, backend.metrics = [], []
        backend.ask_text.side_effect = ["Time ratio is two.",
            "The coefficient is 3/4.\n\nAssumptions used: starts from rest.", "Review agrees: option (c)."]
        result = run("Inclined plane at 45 degrees, twice the time", backend=backend)
        self.assertEqual(backend.ask_text.call_count, 3)
        backend.ask.assert_not_called()
        self.assertEqual(result.status, "completed")
        self.assertIn("3/4", result.markdown)
        self.assertIn("Independent review", result.markdown)
        self.assertIsNone(result.verification)

    def test_plain_stage_has_no_submission_tool_or_json_requirement(self):
        with patch("crewai.Agent") as agent, patch("agentic_jee_system.backend.make_llm"):
            agent.return_value.kickoff.return_value = SimpleNamespace(raw="Ordinary explanation.")
            result = CrewBackend(Settings(min_interval=0)).ask_text("Analyzer", "Analyze", "Question")
            self.assertEqual(result, "Ordinary explanation.")
            self.assertEqual(agent.call_args.kwargs["tools"], [])
