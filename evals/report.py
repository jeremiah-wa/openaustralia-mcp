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


# Regression cases cover what the tools already do. Capability cases are expected to fail until a feature lands.
HEADLINE_TAGS = ("regression", "capability")


@dataclass(frozen=True)
class TagScore:
    tag: str
    cases: int
    mean_pass_rate: float
    share_passed_all: float


def score_tags(scores: list[CaseScore], model: str) -> list[TagScore]:
    """The regression and capability scores for one model, for the tags that have cases."""
    tag_scores = []
    for tag in HEADLINE_TAGS:
        tagged = [score for score in scores if score.model == model and tag in score.tags]
        if tagged:
            tag_scores.append(
                TagScore(
                    tag,
                    len(tagged),
                    sum(score.pass_rate for score in tagged) / len(tagged),
                    sum(score.passed_all for score in tagged) / len(tagged),
                )
            )
    return tag_scores


# US dollars per million input and output tokens, October 2026. Haiku's rate is for prompts up to 100K tokens.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def trial_cost_usd(model: str, usage: dict[str, Any]) -> float:
    """What a trial cost, from the token usage summed over its turns. The runner doesn't use prompt caching."""
    input_price, output_price = PRICES[model]
    return (usage.get("input_tokens", 0) * input_price + usage.get("output_tokens", 0) * output_price) / 1_000_000


def render_summary(records: list[TrialRecord], *, errors: int) -> str:
    """The markdown summary of a run."""
    scores = score_cases(records)
    models = list(dict.fromkeys(score.model for score in scores))
    lines = ["## Scores", "", "| Model | Tag | Cases | Mean pass rate | Passed every trial |", "|---|---|---|---|---|"]
    for model in models:
        for tag in score_tags(scores, model):
            passed_all = round(tag.share_passed_all * tag.cases)
            lines.append(f"| {model} | {tag.tag} | {tag.cases} | {tag.mean_pass_rate:.0%} | {passed_all}/{tag.cases} |")
    if errors:
        lines += ["", f"{errors} trials ended in an error and were run again. They aren't scored."]
    if records:
        cost = sum(trial_cost_usd(record.model, record.usage) for record in records)
        lines += ["", f"Cost: ${cost:.4f} for {len(records)} trials, ${cost / len(records):.4f} per trial."]

    lines += ["", "## Cases", "", f"| Case | Tags | {' | '.join(models)} |", f"|---|---|{'---|' * len(models)}"]
    by_case: dict[str, dict[str, CaseScore]] = {}
    for score in scores:
        by_case.setdefault(score.case_id, {})[score.model] = score
    for case_id, by_model in by_case.items():
        tags = ", ".join(next(iter(by_model.values())).tags)
        cells = [f"{by_model[m].passes}/{by_model[m].trials}" if m in by_model else "" for m in models]
        lines.append(f"| {case_id} | {tags} | {' | '.join(cells)} |")

    failures: dict[tuple[str, str, str], int] = {}
    for record in records:
        for failure in record.failures:
            key = (record.case_id, record.model, failure)
            failures[key] = failures.get(key, 0) + 1
    if failures:
        lines += ["", "## Failures", ""]
        lines += [
            f"- `{case_id}` on {model}, {count} trial{'s' if count > 1 else ''}: {failure}"
            for (case_id, model, failure), count in failures.items()
        ]
    return "\n".join(lines) + "\n"
