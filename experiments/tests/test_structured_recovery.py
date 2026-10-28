"""Stage format recovery stays bounded and retains calculator requirements."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agentic_jee_system.backend import CrewBackend, Settings
from agentic_jee_system.schemas import Claims, Analysis
from agentic_jee_system.reliability import ServiceError

class StructuredRecoveryTests(unittest.TestCase):
    def test_analysis_submission_preserves_labeled_options(self):
        from agentic_jee_system.tools.structured import make_submission
        tool = make_submission(Analysis, [], 0, False)
        value = dict(subject="Mathematics", topic="Linear equation", given=["2x=10"],
            unknowns=["x"], assumptions=[], ambiguities=[], approach="Divide by 2",
            calculation_required=True, options=[{"label": "A", "text": "5"}])
        wire = tool.args_schema.model_validate(value)
        result = Analysis.model_validate_json(tool._run(**wire.model_dump()))
        self.assertEqual(result.options, {"A": "5"})
        self.assertEqual(tool.args_schema.model_json_schema()["properties"]["options"]["type"], "array")

    def test_analyzer_style_stage_registers_submission_and_recovers_once(self):
        with patch("crewai.Agent") as agent, patch("agentic_jee_system.backend.make_llm"):
            agent.return_value.kickoff.side_effect = [
                SimpleNamespace(raw='{"claims":'),
                SimpleNamespace(raw='{"claims":["A claim"]}')]
            backend = CrewBackend(Settings(min_interval=0))
            result = backend.ask("Extractor", "Extract claims", {"input": "A claim"}, Claims)
            self.assertEqual(result.claims, ["A claim"])
            self.assertEqual(agent.call_count, 2)
            self.assertEqual(len(agent.call_args.kwargs["tools"]), 1)
            self.assertIn("FORMAT RECOVERY", agent.return_value.kickoff.call_args.args[0])

    def test_repeated_invalid_output_stops_after_one_recovery(self):
        with patch("crewai.Agent") as agent, patch("agentic_jee_system.backend.make_llm"):
            agent.return_value.kickoff.return_value = SimpleNamespace(raw="invalid")
            backend = CrewBackend(Settings(min_interval=0))
            with self.assertRaises(ServiceError) as ctx:
                backend.ask("Extractor", "Extract claims", {}, Claims)
            self.assertEqual(ctx.exception.code, "invalid_output")
            self.assertEqual(agent.return_value.kickoff.call_count, 2)
