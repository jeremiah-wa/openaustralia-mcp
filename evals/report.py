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
    # Tool calls over all its trials. A failed call counts too: Claude spent a turn on it.
    calls: int = 0
    failed_calls: int = 0
    input_tokens: int = 0

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
        CaseScore(
            case_id,
            group[0].tags,
            model,
            len(group),
            sum(record.passed for record in group),
            calls=sum(len(record.trial.calls) for record in group),
            failed_calls=sum(call.error is not None for record in group for call in record.trial.calls),
            input_tokens=sum(record.usage.get("input_tokens", 0) for record in group),
        )
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
    calls_per_trial: float
    failed_calls_per_trial: float
    # Includes the tool definitions, which every turn sends again.
    input_tokens_per_trial: float


def score_tags(scores: list[CaseScore], model: str) -> list[TagScore]:
    """The regression and capability scores for one model, for the tags that have cases."""
    tag_scores = []
    for tag in HEADLINE_TAGS:
        tagged = [score for score in scores if score.model == model and tag in score.tags]
        if tagged:
            trials = sum(score.trials for score in tagged)
            tag_scores.append(
                TagScore(
                    tag,
                    len(tagged),
                    sum(score.pass_rate for score in tagged) / len(tagged),
                    sum(score.passed_all for score in tagged) / len(tagged),
                    sum(score.calls for score in tagged) / trials,
                    sum(score.failed_calls for score in tagged) / trials,
                    sum(score.input_tokens for score in tagged) / trials,
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


SCORE_COLUMNS = (
    "Model",
    "Tag",
    "Cases",
    "Mean pass rate",
    "Passed every trial",
    "Calls per trial",
    "Failed calls per trial",
    "Input tokens per trial",
)


def render_summary(records: list[TrialRecord], *, errors: int) -> str:
    """The markdown summary of a run."""
    scores = score_cases(records)
    models = list(dict.fromkeys(score.model for score in scores))
    lines = ["## Scores", "", f"| {' | '.join(SCORE_COLUMNS)} |", "|" + "---|" * len(SCORE_COLUMNS)]
    for model in models:
        for tag in score_tags(scores, model):
            passed_all = round(tag.share_passed_all * tag.cases)
            lines.append(
                f"| {model} | {tag.tag} | {tag.cases} | {tag.mean_pass_rate:.0%} | {passed_all}/{tag.cases} "
                f"| {tag.calls_per_trial:.2f} | {tag.failed_calls_per_trial:.2f} | {tag.input_tokens_per_trial:,.0f} |"
            )
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


class ModelRun(BaseModel):
    effort: str
    trials: int
    cost_per_trial_usd: float


class CaseResult(BaseModel):
    tags: list[str]
    passes: int
    trials: int


class Scores(BaseModel):
    """A run's scores, saved as scores.json. The committed evals/results/baseline.json is one of these."""

    models: dict[str, ModelRun]
    # By case id, then by model.
    cases: dict[str, dict[str, CaseResult]]


def scores(records: list[TrialRecord]) -> Scores:
    models: dict[str, ModelRun] = {}
    for model in dict.fromkeys(record.model for record in records):
        mine = [record for record in records if record.model == model]
        cost = sum(trial_cost_usd(model, record.usage) for record in mine)
        models[model] = ModelRun(effort=mine[0].effort, trials=len(mine), cost_per_trial_usd=cost / len(mine))
    cases: dict[str, dict[str, CaseResult]] = {}
    for score in score_cases(records):
        cases.setdefault(score.case_id, {})[score.model] = CaseResult(
            tags=score.tags, passes=score.passes, trials=score.trials
        )
    return Scores(models=models, cases=cases)


def render_comparison(baseline: Scores, run: Scores) -> str:
    """The markdown comparison of a run with the baseline, over the cases and models both have."""
    lines = ["## Compared with the baseline", ""]
    models = [model for model in run.models if model in baseline.models]
    for model in models:
        effort, baseline_effort = run.models[model].effort, baseline.models[model].effort
        if effort != baseline_effort:
            warning = f"{model} ran at effort {effort}, and the baseline at {baseline_effort}"
            lines += [f"{warning}, so the scores aren't comparable.", ""]

    lines += ["| Model | Tag | Cases | Baseline | This run | Change |", "|---|---|---|---|---|---|"]
    for model in models:
        shared = [case for case in run.cases if model in run.cases[case] and model in baseline.cases.get(case, {})]
        for tag in HEADLINE_TAGS:
            tagged = [case for case in shared if tag in run.cases[case][model].tags]
            if not tagged:
                continue
            then = _mean_pass_rate(baseline, tagged, model)
            now = _mean_pass_rate(run, tagged, model)
            change = round((now - then) * 100)
            points = f"{change:+d}" if change else "0"
            lines.append(f"| {model} | {tag} | {len(tagged)} | {then:.0%} | {now:.0%} | {points} points |")

    changed = [
        (case, model)
        for model in models
        for case in run.cases
        if model in run.cases[case]
        and model in baseline.cases.get(case, {})
        and run.cases[case][model].passes / run.cases[case][model].trials
        != baseline.cases[case][model].passes / baseline.cases[case][model].trials
    ]
    if changed:
        lines += ["", "| Case | Model | Baseline | This run |", "|---|---|---|---|"]
        for case, model in changed:
            then, now = baseline.cases[case][model], run.cases[case][model]
            lines.append(f"| {case} | {model} | {then.passes}/{then.trials} | {now.passes}/{now.trials} |")

    new = [case for case in run.cases if case not in baseline.cases]
    if new:
        lines += ["", f"Not in the baseline: {', '.join(f'`{case}`' for case in new)}."]
    lines += ["", "With about 100 trials per model, differences under about 10 points are noise (docs/evals.md)."]
    return "\n".join(lines) + "\n"


def _mean_pass_rate(run: Scores, cases: list[str], model: str) -> float:
    return sum(run.cases[case][model].passes / run.cases[case][model].trials for case in cases) / len(cases)


def estimate_usd(*, cases: int, trials: int, cost_per_trial: dict[str, float | None]) -> float | None:
    """What a run will cost, from each model's measured cost per trial. None if a model has no measured cost."""
    if any(cost is None for cost in cost_per_trial.values()):
        return None
    return sum(cases * trials * cost for cost in cost_per_trial.values() if cost is not None)
