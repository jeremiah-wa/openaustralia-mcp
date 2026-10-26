"""Scores from graded trials, and the markdown summary of a run. See docs/evals.md#trials-and-scores."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from evals.graders import Trial


class TrialRecord(BaseModel):
    """One graded trial: a line of trials.jsonl."""

    case_id: str
    tags: list[str]
    model: str
    effort: str
    trial: Trial
    failures: list[str]
    stop_reason: str | None = None
    usage: dict[str, Any] = {}

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    tags: list[str]
    model: str
    trials: int
    passes: int

    @property
    def pass_rate(self) -> float:
        return self.passes / self.trials

    @property
    def passed_all(self) -> bool:
        """pass^k: every trial passed."""
        return self.passes == self.trials


def score_cases(records: list[TrialRecord]) -> list[CaseScore]:
    """One score per case and model, in the order they first appear."""
    grouped: dict[tuple[str, str], list[TrialRecord]] = {}
    for record in records:
        grouped.setdefault((record.case_id, record.model), []).append(record)
    return [
        CaseScore(case_id, group[0].tags, model, len(group), sum(record.passed for record in group))
        for (case_id, model), group in grouped.items()
    ]
