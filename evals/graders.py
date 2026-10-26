"""Deterministic graders: score one trial's tool calls and answer against its case. See docs/evals.md#graders."""

from typing import Any

from pydantic import BaseModel

from evals.cases import Case, ExpectedCall, ForbiddenCall


class Call(BaseModel):
    """A tool call as Claude sent it, and the structured result it got back."""

    tool: str
    input: dict[str, Any]
    result: dict[str, Any] | None = None

    def describe(self) -> str:
        return f"{self.tool}({', '.join(f'{name}={value!r}' for name, value in self.input.items())})"


class Trial(BaseModel):
    calls: list[Call]
    answer: str


def grade(case: Case, trial: Trial, schemas: dict[str, dict[str, Any]]) -> list[str]:
    """The reasons the trial failed. An empty list means it passed."""
    failures = []
    expected_calls = case.expect.calls
    # For each expected call, the positions in the trial where it was made.
    made = [[i for i, call in enumerate(trial.calls) if _matches(expected, call)] for expected in expected_calls]
    made_by_id = {expected.id: made[n] for n, expected in enumerate(expected_calls) if expected.id}
    for expected, positions in zip(expected_calls, made, strict=True):
        if not positions:
            failures.append(f"missing call: {expected.describe()}")
        elif expected.after:
            needed = made_by_id[expected.after]
            if needed and max(positions) <= min(needed):
                failures.append(f"out of order: {expected.describe()} came before {expected.after}")

    for call in trial.calls:
        if any(_is_forbidden(forbidden, call) for forbidden in case.expect.forbidden):
            failures.append(f"forbidden call: {call.describe()}")
    return failures


def _matches(expected: ExpectedCall, call: Call) -> bool:
    if call.tool != expected.tool:
        return False
    if any(call.input.get(name) != value for name, value in expected.args.items()):
        return False
    return all(_contains_one(call.input.get(name), texts) for name, texts in expected.args_contain.items())


def _is_forbidden(forbidden: ForbiddenCall, call: Call) -> bool:
    return (
        call.tool == forbidden.tool
        and all(call.input.get(name) == value for name, value in forbidden.args.items())
        and all(call.input.get(name) is None for name in forbidden.args_missing)
    )


def _contains_one(value: Any, texts: list[str]) -> bool:
    return isinstance(value, str) and any(text.lower() in value.lower() for text in texts)
