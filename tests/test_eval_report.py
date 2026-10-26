"""The eval report: pass rates per case, model and tag (see docs/evals.md#trials-and-scores)."""

from evals.graders import Trial
from evals.report import TrialRecord, score_cases, score_tags

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"


def record(case_id: str, passed: bool, *, model: str = SONNET, tags: tuple[str, ...] = ("regression",)) -> TrialRecord:
    return TrialRecord(
        case_id=case_id,
        tags=list(tags),
        model=model,
        effort="high",
        trial=Trial(calls=[], answer=""),
        failures=[] if passed else ["missing call: get_members(postcode='3056')"],
    )


class TestPassRate:
    def test_is_the_share_of_trials_that_passed(self) -> None:
        records = [record("mp-3056", passed) for passed in (True, True, True, False, False)]

        [score] = score_cases(records)

        assert (score.case_id, score.trials, score.passes, score.pass_rate) == ("mp-3056", 5, 3, 0.6)


class TestPassAllTrials:
    def test_only_when_every_trial_passed(self) -> None:
        records = [record("all", True) for _ in range(5)] + [
            record("most", passed) for passed in (True,) * 4 + (False,)
        ]

        scores = {score.case_id: score.passed_all for score in score_cases(records)}

        assert scores == {"all": True, "most": False}


class TestPerModel:
    def test_scores_each_model_separately(self) -> None:
        records = [record("mp-3056", True, model=SONNET), record("mp-3056", False, model=HAIKU)]

        scores = {score.model: score.pass_rate for score in score_cases(records)}

        assert scores == {SONNET: 1.0, HAIKU: 0.0}


class TestByTag:
    def test_keep_capability_cases_out_of_the_regression_score(self) -> None:
        records = [
            *(record("mp-3056", True) for _ in range(2)),
            *(record("ndis", passed) for passed in (True, False)),
            *(record("senators", False, tags=("capability",)) for _ in range(2)),
        ]

        regression, capability = score_tags(score_cases(records), SONNET)

        assert (regression.tag, regression.cases, regression.mean_pass_rate, regression.share_passed_all) == (
            "regression",
            2,
            0.75,
            0.5,
        )
        assert (capability.tag, capability.cases, capability.mean_pass_rate) == ("capability", 1, 0.0)

    def test_only_count_the_given_model(self) -> None:
        records = [record("mp-3056", True, model=SONNET), record("mp-3056", False, model=HAIKU)]

        [regression] = score_tags(score_cases(records), HAIKU)

        assert regression.mean_pass_rate == 0.0
