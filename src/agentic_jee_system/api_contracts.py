"""Shared HTTP contracts for the Render backend and Streamlit client."""
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from .schemas import Contract, Result


class JobRequest(Contract):
    question: str = Field(min_length=3, max_length=4000)
    mode: Literal["solve", "fact_check"] = "solve"
    subject: Literal["Auto", "Mathematics", "Physics", "Chemistry"] = "Auto"

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        from .workflow import validate_input
        return validate_input(value)


class JobSnapshot(Contract):
    job_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
    result: Result | None = None
    error: str | None = None
    error_code: str | None = None
