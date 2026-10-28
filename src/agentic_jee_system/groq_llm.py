"""Groq-only compatibility boundary for CrewAI prompt-cache annotations.

CrewAI 1.15.22 adds cache_breakpoint to messages, but its LiteLLM path can send
that internal annotation to Groq unchanged. Groq rejects that field with 400.
Clean the final request parameters for this LLM instance only; do not patch
global CrewAI functions or change caching behavior for other providers.
"""
from copy import deepcopy

from crewai import LLM


class GroqCompatibleLLM(LLM):
    def _prepare_completion_params(self, messages, tools=None, skip_file_processing=False):
        params = super()._prepare_completion_params(
            messages=deepcopy(messages), tools=tools, skip_file_processing=skip_file_processing)
        for message in params.get("messages", []):
            message.pop("cache_breakpoint", None)
        return params
