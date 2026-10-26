"""Deterministic graders: score one trial's tool calls and answer against its case. See docs/evals.md#graders."""

from typing import Any

from pydantic import BaseModel

from evals.cases import Case, ExpectedCall


class Call(BaseModel):
    """A tool call as Claude sent it, and the structured result it got back."""

    tool: str
    input: dict[str, Any]
    result: dict[str, Any] | None = None


class Trial(BaseModel):
    calls: list[Call]
    answer: str


def grade(case: Case, trial: Trial, schemas: dict[str, dict[str, Any]]) -> list[str]:
    """The reasons the trial failed. An empty list means it passed."""
    failures = []
    for expected in case.expect.calls:
        if not any(_matches(expected, call) for call in trial.calls):
            failures.append(f"missing call: {expected.describe()}")
    return failures


def _matches(expected: ExpectedCall, call: Call) -> bool:
    if call.tool != expected.tool:
        return False
    if any(call.input.get(name) != value for name, value in expected.args.items()):
        return False
    return all(_contains_one(call.input.get(name), texts) for name, texts in expected.args_contain.items())


def _contains_one(value: Any, texts: list[str]) -> bool:
    return isinstance(value, str) and any(text.lower() in value.lower() for text in texts)
