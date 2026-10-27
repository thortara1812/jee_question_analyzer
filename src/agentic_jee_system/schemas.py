"""Validated contracts between reasoning stages and the user interface."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Analysis(Contract):
    subject: Literal["Mathematics", "Physics", "Chemistry", "Unknown"]
    topic: str
    given: list[str]
    unknowns: list[str]
    assumptions: list[str]
    options: dict[str, str]
    ambiguities: list[str]
    approach: str
    calculation_required: bool


class Solution(Contract):
    formula: str = Field(description="Governing equation only, without arrow chains or worked substitutions.")
    steps: list[str] = Field(min_length=1, max_length=12,
        description="Each step explains the operation in plain English, then displays its equation using $$ delimiters. No arrows or raw unwrapped LaTeX.")
    answer: str
    option: str | None
    limitations: list[str]


class Verification(Contract):
    verdict: Literal["verified", "rejected", "needs_review"]
    checks: list[str] = Field(min_length=1)
    errors: list[str]
    correction: str


class Evidence(Contract):
    title: str
    url: HttpUrl
    excerpt: str = Field(min_length=1)


class Claims(Contract):
    claims: list[str] = Field(min_length=1, max_length=5)


class FactVerdict(Contract):
    verdict: Literal["supported", "contradicted", "inconclusive"]
    explanation: str
    citations: list[HttpUrl]


class ToolExecution(Contract):
    tool: str
    success: bool
    stage: str | None = None
    expression: str | None = None
    value: float | None = None
    operation: str | None = None
    result: dict[str, float] | None = None


class Result(Contract):
    mode: Literal["solve", "fact_check"]
    status: str
    markdown: str
    tool_calls: list[ToolExecution] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    metrics: list[dict] = Field(default_factory=list)
    analysis: Analysis | None = None
    solution: Solution | None = None
    verification: Verification | None = None
