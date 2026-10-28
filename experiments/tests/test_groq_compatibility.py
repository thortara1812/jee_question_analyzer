"""Exercise real CrewAI request preparation with injected cache metadata."""
from copy import deepcopy
import unittest

from crewai import LLM
from crewai.llms.cache import mark_cache_breakpoint

from agentic_jee_system.backend import Settings, make_llm
from agentic_jee_system.groq_llm import GroqCompatibleLLM
from agentic_jee_system.reliability import ServiceError, retry_call


class GroqCompatibilityTests(unittest.TestCase):
    def test_factory_selects_scoped_groq_adapter(self):
        self.assertIsInstance(make_llm(Settings()), GroqCompatibleLLM)

    def test_final_payload_removes_annotation_without_mutating_messages(self):
        messages = [
            {"role": "system", "content": "Check the question", "cache_breakpoint": True},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "test", "type": "function", "function": {"name": "bounded_calculator", "arguments": '{"expression":"2+2"}'}}], "cache_breakpoint": True},
            {"role": "tool", "tool_call_id": "test", "content": "4", "cache_breakpoint": True},
        ]
        original = deepcopy(messages)
        tools = [{"type": "function", "function": {"name": "bounded_calculator", "parameters": {"type": "object"}}}]
        llm = make_llm(Settings())
        for async_prepared in (False, True):
            with self.subTest(async_prepared=async_prepared):
                params = llm._prepare_completion_params(messages, tools, skip_file_processing=async_prepared)
                self.assertTrue(all("cache_breakpoint" not in message for message in params["messages"]))
                self.assertEqual(params["messages"][1]["tool_calls"], original[1]["tool_calls"])
                self.assertEqual(params["messages"][2]["content"], "4")
                self.assertEqual(params["tools"], tools)
                self.assertEqual(messages, original)

    def test_other_provider_and_global_cache_function_are_unchanged(self):
        llm = LLM(model="groq/openai/gpt-oss-120b", num_retries=0)
        marked = {"role": "system", "content": "Original", "cache_breakpoint": True}
        self.assertIn("cache_breakpoint", llm._prepare_completion_params([marked])["messages"][0])
        # Both clean and previously modified local installations remain untouched.
        before = mark_cache_breakpoint({"role": "system", "content": "Original"})
        make_llm(Settings())._prepare_completion_params([marked])
        self.assertEqual(mark_cache_breakpoint({"role": "system", "content": "Original"}), before)

    def test_unsupported_metadata_is_classified_and_not_retried(self):
        class BadRequestError(Exception):
            status_code = 400
        calls = []
        def fail():
            calls.append(1)
            raise BadRequestError("messages.0 cache_breakpoint unsupported SECRET")
        with self.assertRaises(ServiceError) as ctx:
            retry_call(fail)
        self.assertEqual(ctx.exception.code, "provider_compatibility")
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertEqual(len(calls), 1)
