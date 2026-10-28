"""Explicit schema submission tool for native tool-capable reasoning models."""
from pydantic import BaseModel, create_model
from crewai.tools import BaseTool
from ..schemas import Analysis


class Choice(BaseModel):
    label: str
    text: str


def make_submission(schema: type[BaseModel], audit: list[dict], start: int, required: bool):
    # Groq native tools reject CrewAI's strict-schema conversion of open maps.
    # Use an explicit list on the wire while retaining Analysis.options internally.
    wire_schema = (create_model("AnalysisSubmission", __base__=Analysis,
                               options=(list[Choice], ...)) if schema is Analysis else schema)
    class SubmissionTool(BaseTool):
        name: str = "JSON"
        description: str = "Submit the final structured result. For numerical problems, successfully use a calculator first."
        args_schema: type[BaseModel] = wire_schema
        result_as_answer: bool = True

        def _run(self, **kwargs) -> str:
            if required and not any(record.get("success") for record in audit[start:]):
                raise ValueError("Calculate with bounded_calculator or science_calculator before submitting the result.")
            if schema is Analysis:
                choices = [Choice.model_validate(item) for item in kwargs["options"]]
                if len({item.label for item in choices}) != len(choices):
                    raise ValueError("Option labels must be unique.")
                kwargs["options"] = {item.label: item.text for item in choices}
            return schema.model_validate(kwargs).model_dump_json()

    return SubmissionTool()
