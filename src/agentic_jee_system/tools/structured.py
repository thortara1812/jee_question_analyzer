"""Explicit schema submission tool for native tool-capable reasoning models."""
from pydantic import BaseModel
from crewai.tools import BaseTool


def make_submission(schema: type[BaseModel], audit: list[dict], start: int, required: bool):
    class SubmissionTool(BaseTool):
        name: str = "JSON"
        description: str = "Submit the final structured result. For numerical problems, successfully use a calculator first."
        args_schema: type[BaseModel] = schema
        result_as_answer: bool = True

        def _run(self, **kwargs) -> str:
            if required and not any(record.get("success") for record in audit[start:]):
                raise ValueError("Calculate with bounded_calculator or science_calculator before submitting the result.")
            return schema.model_validate(kwargs).model_dump_json()

    return SubmissionTool()
