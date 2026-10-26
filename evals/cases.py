"""An eval case, in the shape of its YAML file under evals/cases/. The fields are described in docs/evals.md#cases."""

from typing import Any

from pydantic import BaseModel, model_validator


class ExpectedCall(BaseModel):
    id: str | None = None
    tool: str
    args: dict[str, Any] = {}
    args_contain: dict[str, list[str]] = {}
    # The id of a call whose output this one needs, so it must come after it. Only for real dependencies.
    after: str | None = None

    def describe(self) -> str:
        parts = [f"{name}={value!r}" for name, value in self.args.items()]
        parts += [f"{name} contains one of {texts}" for name, texts in self.args_contain.items()]
        return f"{self.tool}({', '.join(parts)})"


class ForbiddenCall(BaseModel):
    """Matches a call to the tool whose `args` match exactly and which has none of the `args_missing`."""

    tool: str
    args: dict[str, Any] = {}
    args_missing: list[str] = []


class Expect(BaseModel):
    calls: list[ExpectedCall] = []
    forbidden: list[ForbiddenCall] = []
    max_calls: int | None = None
    # Facts from the fixtures, such as a member's name. Not phrasing.
    answer_contains: list[str] = []
    cites_url: bool = False

    @model_validator(mode="after")
    def _after_names_a_call(self) -> "Expect":
        ids = {call.id for call in self.calls}
        for call in self.calls:
            if call.after is not None and call.after not in ids:
                raise ValueError(f"after: no expected call has id {call.after!r}")
        return self


class Fixture(BaseModel):
    """A recorded response the case can use, by file name under tests/fixtures/openaustralia/."""

    file: str
    # A search fixture answers any search containing one of these, instead of only its recorded one.
    search_contains: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _bare_name(cls, value: Any) -> Any:
        return {"file": value} if isinstance(value, str) else value

    @property
    def path(self) -> str:
        """The name `FakeApi.route` takes."""
        return f"openaustralia/{self.file}"


class Case(BaseModel):
    id: str
    tags: list[str]
    question: str
    # Any request these don't answer gets a 404.
    fixtures: list[Fixture] = []
    expect: Expect
