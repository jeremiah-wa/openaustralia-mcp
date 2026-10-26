"""An eval case, in the shape of its YAML file under evals/cases/. The fields are described in docs/evals.md#cases."""

from typing import Any

from pydantic import BaseModel


class ExpectedCall(BaseModel):
    tool: str
    args: dict[str, Any] = {}
    args_contain: dict[str, list[str]] = {}

    def describe(self) -> str:
        parts = [f"{name}={value!r}" for name, value in self.args.items()]
        parts += [f"{name} contains one of {texts}" for name, texts in self.args_contain.items()]
        return f"{self.tool}({', '.join(parts)})"


class Expect(BaseModel):
    calls: list[ExpectedCall] = []


class Case(BaseModel):
    id: str
    tags: list[str]
    question: str
    expect: Expect
