"""Offline regression tests. No provider requests or real keys required."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from agentic_jee_system.backend import CrewBackend, Settings
from agentic_jee_system.evidence import authoritative, retrieve
from agentic_jee_system.history import clear, recent, save
from agentic_jee_system.reliability import ServiceError, category, retry_call
from agentic_jee_system.schemas import Analysis, Claims, Evidence, FactVerdict, Solution, Verification
from agentic_jee_system.tools.calculator import calculate
from agentic_jee_system.tools.science import science
from agentic_jee_system.workflow import run


def analysis(**changes):
    values = dict(subject="Physics", topic="Work and energy", given=["2 kg", "8 N", "5 s"],
                  unknowns=["Kinetic energy"], assumptions=["Frictionless"], options={},
                  ambiguities=[], approach="Newton's law then kinetic energy", calculation_required=True)
    return Analysis(**(values | changes))


def solution(**changes):
    return Solution(**(dict(formula="$K=mv^2/2$", steps=["a=8/2=4 m/s²", "v=4*5=20 m/s", "K=400 J"],
                           answer="400 J", option=None, limitations=[]) | changes))


def verification(verdict="verified", **changes):
    return Verification(**(dict(verdict=verdict, checks=["Recomputed work = F * (a*t²/2) = 400 J"],
                                errors=[] if verdict == "verified" else ["Wrong energy"],
                                correction="" if verdict == "verified" else "Recalculate energy.") | changes))


class FakeBackend:
    def __init__(self, outputs, record_tools=True):
        self.outputs = iter(outputs)
        self.calls, self.metrics, self.tool_calls = [], [], []
        self.record_tools = record_tools

    def ask(self, role, instruction, payload, schema, *, tools=False):
        self.calls.append(role)
        if tools and self.record_tools:
            self.tool_calls.append({"stage": role, "tool": "mock", "success": True})
        return schema.model_validate(next(self.outputs).model_dump())


class CalculatorTests(unittest.TestCase):
    def test_historical_physics_calculation(self):
        self.assertEqual(calculate("0.5*2*((8/2)*5)**2"), 400)

    def test_arithmetic(self):
        self.assertAlmostEqual(calculate("-(2+3)/2 + 9**0.5"), 0.5)

    def test_rejects_unsafe_or_unbounded_expressions(self):
        for text in ["__import__('os').system('whoami')", "[1]*10", "True", "1/0", "2**100000", "1e999", "(-1)**0.5", "abs(1)", "x+1", "1"*301]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                calculate(text)

    def test_domain_formulas(self):
        cases = [
            ("linear_equation", {"a": 2, "b": 5, "c": 15}, "x", 5),
            ("force_motion", {"mass": 2, "force": 8, "time": 5, "initial_velocity": 0}, "energy_j", 400),
            ("kinetic_energy", {"mass": 2, "velocity": 20}, "energy_j", 400),
            ("centripetal_acceleration", {"radius": .5, "angular_velocity": 4}, "acceleration_ms2", 8),
            ("moles", {"mass_g": 18, "molar_mass_g_mol": 18}, "moles", 1),
            ("molarity", {"moles": .5, "volume_l": 2}, "molarity_mol_l", .25),
            ("ideal_gas_moles", {"pressure_pa": 8314.462618, "volume_m3": 1, "temperature_k": 1000}, "moles", 1),
            ("kmh_to_ms", {"speed": 36}, "speed_ms", 10),
        ]
        for op, params, key, expected in cases:
            with self.subTest(op=op):
                self.assertAlmostEqual(science(op, params)[key], expected)

    def test_invalid_domain_parameters(self):
        for op, params in [("moles", {"mass_g": 2, "molar_mass_g_mol": 0}),
                           ("linear_equation", {"a": 0, "b": 1, "c": 2}),
                           ("molarity", {"moles": -1, "volume_l": 2}),
                           ("moles", {"mass_g": True, "molar_mass_g_mol": 2}),
                           ("moles", {"mass_g": "18", "molar_mass_g_mol": 18}),
                           ("unknown", {}), ("moles", {})]:
            with self.subTest(op=op, params=params), self.assertRaises(ValueError):
                science(op, params)


class WorkflowTests(unittest.TestCase):
    def test_three_stages_and_no_composer_call(self):
        backend = FakeBackend([analysis(), solution(), verification()])
        result = run("Block energy question", backend=backend)
        self.assertEqual(result.status, "verified")
        self.assertIn("400 J", result.markdown)
        self.assertEqual(len(backend.calls), 3)

    def test_ambiguity_stops_before_solver(self):
        backend = FakeBackend([analysis(ambiguities=["Mass unknown"] )])
        result = run("Find kinetic energy", backend=backend)
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(len(backend.calls), 1)

    def test_only_one_correction_with_reverification(self):
        backend = FakeBackend([analysis(), solution(answer="40 J"), verification("rejected"), solution(), verification()])
        result = run("Block energy question", backend=backend)
        self.assertEqual(result.status, "verified")
        self.assertEqual(len(backend.calls), 5)

    def test_second_rejection_is_never_formatted_as_success(self):
        backend = FakeBackend([analysis(), solution(), verification("rejected"), solution(), verification("rejected")])
        result = run("Block energy question", backend=backend)
        self.assertEqual(result.status, "needs_review")
        self.assertNotIn("**Final answer:**", result.markdown)
        self.assertEqual(len(backend.calls), 5)

    def test_missing_tools_prevents_numeric_verification(self):
        backend = FakeBackend([analysis(), solution(), verification()], record_tools=False)
        self.assertEqual(run("Block energy question", backend=backend).status, "needs_review")

    def test_no_matching_option_is_allowed(self):
        backend = FakeBackend([analysis(options={"A": "200 J"}), solution(), verification()])
        result = run("Block energy question", backend=backend)
        self.assertEqual(result.status, "verified")
        self.assertIn("No provided option matches", result.markdown)

    def test_unknown_option_fails_closed(self):
        backend = FakeBackend([analysis(options={"A": "400 J"}), solution(option="B"), verification()])
        self.assertEqual(run("Block energy question", backend=backend).status, "needs_review")

    def test_limitations_block_final_answer(self):
        backend = FakeBackend([analysis(), solution(limitations=["Missing force duration"]), verification()])
        self.assertEqual(run("Block energy question", backend=backend).status, "needs_review")

    def test_input_limits_and_modes(self):
        for value in ["", "x", "x"*4001, "abc\x00"]:
            with self.subTest(value=value[:10]), self.assertRaises(ValueError):
                run(value)
        with self.assertRaises(ValueError):
            run("question", mode="unknown")

    def test_unavailable_search_is_inconclusive(self):
        backend = FakeBackend([Claims(claims=["Energy is conserved"])])
        result = run("Energy is conserved", "fact_check", backend=backend, search=lambda _: [])
        self.assertEqual(result.status, "inconclusive")
        self.assertEqual(len(backend.calls), 1)

    def test_fabricated_citation_is_rejected(self):
        evidence = Evidence(title="NCERT", url="https://ncert.nic.in/textbook.php", excerpt="Energy passage")
        backend = FakeBackend([Claims(claims=["Energy claim"]), FactVerdict(verdict="supported", explanation="Claim", citations=["https://fake.example/"])])
        result = run("Energy claim", "fact_check", backend=backend, search=lambda _: [evidence])
        self.assertEqual(result.status, "inconclusive")

    def test_valid_citation_preserved(self):
        evidence = Evidence(title="NCERT", url="https://ncert.nic.in/textbook.php", excerpt="Energy passage")
        backend = FakeBackend([Claims(claims=["Energy claim"]), FactVerdict(verdict="supported", explanation="Supported by passage", citations=[evidence.url])])
        result = run("Energy claim", "fact_check", backend=backend, search=lambda _: [evidence])
        self.assertEqual(result.status, "supported")
        self.assertEqual(result.evidence, [evidence])

    def test_fabricated_inline_link_is_rejected(self):
        evidence = Evidence(title="NCERT", url="https://ncert.nic.in/textbook.php", excerpt="Energy passage")
        backend = FakeBackend([Claims(claims=["Energy claim"]), FactVerdict(verdict="supported",
            explanation="See [made-up source](https://fake.example/)", citations=[evidence.url])])
        result = run("Energy claim", "fact_check", backend=backend, search=lambda _: [evidence])
        self.assertEqual(result.status, "inconclusive")

    def test_conflicting_evidence_inconclusive_is_preserved(self):
        evidence = Evidence(title="Reference", url="https://example.edu/", excerpt="Conflicting passage")
        backend = FakeBackend([Claims(claims=["Energy claim"]), FactVerdict(verdict="inconclusive", explanation="Sources conflict", citations=[evidence.url])])
        self.assertEqual(run("Energy claim", "fact_check", backend=backend, search=lambda _: [evidence]).status, "inconclusive")


class ReliabilityTests(unittest.TestCase):
    def test_429_retry_after_and_metrics(self):
        class RateLimitError(Exception):
            status_code = 429
            response = SimpleNamespace(headers={"retry-after": "3"})
        calls, delays, metrics = [], [], []
        def request():
            calls.append(1)
            if len(calls) < 3:
                raise RateLimitError("secret must not be exposed")
            return 42
        self.assertEqual(retry_call(request, sleep=delays.append, metrics=metrics), 42)
        self.assertEqual(delays, [3, 3])
        self.assertEqual(len(metrics), 3)

    def test_authentication_not_retried_or_leaked(self):
        class AuthenticationError(Exception):
            status_code = 401
        calls = []
        def request():
            calls.append(1)
            raise AuthenticationError("SECRET")
        with self.assertRaises(ServiceError) as ctx:
            retry_call(request)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_transient_retries_exhaust(self):
        delays = []
        with self.assertRaises(ServiceError):
            retry_call(lambda: (_ for _ in ()).throw(TimeoutError()), sleep=delays.append)
        self.assertEqual(len(delays), 2)
        self.assertEqual(category(TimeoutError()), "transient")

    def test_malformed_stage_output_fails_closed(self):
        backend = CrewBackend(Settings(min_interval=0))
        with patch("crewai.Agent") as agent, patch("agentic_jee_system.backend.make_llm"):
            agent.return_value.kickoff.return_value = SimpleNamespace(raw='{"answer":"400"}', usage_metrics=None)
            with self.assertRaises(ServiceError):
                backend.ask("Test", "Return analysis", {}, Analysis)

    def test_registered_tools_can_execute_without_network(self):
        from agentic_jee_system.tools.calculator import make_calculator
        from agentic_jee_system.tools.science import make_science_tool
        records = []
        self.assertEqual(float(make_calculator(records).run(expression="8/2")), 4)
        result = json.loads(make_science_tool(records).run(operation="moles", values_json='{"mass_g":18,"molar_mass_g_mol":18}'))
        self.assertEqual(result["moles"], 1)
        self.assertEqual(len(records), 2)

    def test_structured_submission_requires_real_calculation(self):
        from agentic_jee_system.tools.structured import make_submission
        records = []
        tool = make_submission(Solution, records, 0, True)
        with self.assertRaises(ValueError):
            tool.run(**solution().model_dump())
        records.append({"success": True, "tool": "calculator"})
        self.assertEqual(Solution.model_validate_json(tool.run(**solution().model_dump())).answer, "400 J")
        self.assertTrue(tool.result_as_answer)

    def test_submission_cannot_reuse_earlier_stage_calculation(self):
        from agentic_jee_system.tools.structured import make_submission
        records = [{"success": True, "tool": "calculator"}]
        tool = make_submission(Verification, records, 1, True)
        with self.assertRaises(ValueError):
            tool.run(**verification().model_dump())


class InfrastructureTests(unittest.TestCase):
    def test_missing_schema_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            Analysis(subject="Physics")

    def test_source_host_validation(self):
        self.assertTrue(authoritative("https://ncert.nic.in/book"))
        self.assertFalse(authoritative("https://ncert.nic.in.evil.example/book"))

    def test_no_search_key_does_not_invent_evidence(self):
        with patch.dict("os.environ", {"TAVILY_API_KEY": ""}):
            self.assertEqual(retrieve(["Claim"]), [])

    def test_history_roundtrip_and_clear(self):
        backend = FakeBackend([analysis(), solution(), verification()])
        result = run("Block question", backend=backend)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            save("Block question", result, path)
            self.assertEqual(recent(path)[0]["result"]["status"], "verified")
            clear(path)
            self.assertEqual(recent(path), [])


if __name__ == "__main__":
    unittest.main()
