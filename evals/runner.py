"""Runs the eval cases against Claude, through the in-memory MCP client. See docs/evals.md#how-a-run-works."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
import anyio
import httpx2
import yaml
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import Client
from mcp.client.session import ClientSession
from mcp.types import CallToolResult

from evals.cases import Case
from evals.graders import Call, Trial, grade
from evals.report import (
    Scores,
    TrialRecord,
    estimate_usd,
    render_comparison,
    render_summary,
    scores,
    trial_cost_usd,
)
from evals.variants import VARIANTS
from openaustralia_mcp.config import Config
from tests.fake_api import FakeApi

CASES = Path(__file__).parent / "cases"
RUNS = Path(__file__).parent / "results" / "runs"
# The committed scores of the baseline run. Runs compare with it, and CI estimates costs from it.
BASELINE = Path(__file__).parent / "results" / "baseline.json"

# Each model's default effort, set explicitly so a change in defaults can't change the scores unnoticed.
EFFORT = {"claude-sonnet-5-5": "high", "claude-haiku-5-5": "medium"}
TURN_CAP = 8
MAX_TOKENS = 16000
# A trial that ends in an error is run again, up to this many times in all.
ATTEMPTS = 3

# Every request is answered from fixtures, so the server gets a placeholder key.
CONFIG = Config(openaustralia_api_key="eval-placeholder-not-a-key")


class WrongModelError(Exception):
    """The API answered with a different model from the one requested. Scores would be meaningless."""


class RecordingSession:
    """Passes Claude's tool calls on to the MCP session, and records each one with its result."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self.calls: list[Call] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, **kwargs: Any) -> CallToolResult:
        result = await self._session.call_tool(name, arguments, **kwargs)
        assert isinstance(result, CallToolResult)
        error = " ".join(block.text for block in result.content if block.type == "text") if result.is_error else None
        # `arguments` is Claude's input as sent: async_mcp_tool passes it through without checking it.
        self.calls.append(Call(tool=name, input=dict(arguments or {}), result=result.structured_content, error=error))
        return result


def load_cases(patterns: list[str] | None = None) -> list[Case]:
    """The cases matching any of the globs, in file name order."""
    paths = sorted({path for pattern in patterns or ["*"] for path in CASES.glob(f"{pattern}.yaml")})
    return [Case.model_validate(yaml.safe_load(path.read_text("utf-8"))) for path in paths]


async def run_trial(claude: anthropic.AsyncAnthropic, case: Case, model: str, variant: str) -> TrialRecord:
    fake_api = FakeApi()
    for fixture in case.fixtures:
        fake_api.route(fixture.path, search_contains=fixture.search_contains, contains=fixture.contains)

    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(VARIANTS[variant](http, CONFIG)) as client,
    ):
        tools = (await client.list_tools()).tools
        session = RecordingSession(client.session)
        runner = claude.beta.messages.tool_runner(
            model=model,
            max_tokens=MAX_TOKENS,
            max_iterations=TURN_CAP,
            output_config={"effort": EFFORT[model]},
            system=client.instructions or "",
            tools=[async_mcp_tool(tool, session) for tool in tools],  # type: ignore[arg-type]
            messages=[{"role": "user", "content": case.question}],
        )
        usage = {"input_tokens": 0, "output_tokens": 0}
        last = None
        async for message in runner:
            if message.model != model:
                raise WrongModelError(f"asked for {model}, got {message.model}")
            usage["input_tokens"] += message.usage.input_tokens
            usage["output_tokens"] += message.usage.output_tokens
            last = message

    assert last is not None
    answer = "".join(block.text for block in last.content if block.type == "text")
    # The runner stops at the turn cap even if Claude still wants to call a tool.
    trial = Trial(calls=session.calls, answer=answer, hit_turn_cap=last.stop_reason == "tool_use")
    schemas = {tool.name: tool.input_schema for tool in tools}
    return TrialRecord(
        case_id=case.id,
        tags=case.tags,
        model=model,
        effort=EFFORT[model],
        variant=variant,
        trial=trial,
        failures=grade(case, trial, schemas),
        stop_reason=last.stop_reason,
        usage=usage,
    )


def measured_cost_per_trial(model: str) -> float | None:
    """The cost per trial on this model in the latest local run that used it, else in the baseline, else None."""
    for path in [*sorted(RUNS.glob("*/scores.json"), reverse=True), BASELINE]:
        if path.exists():
            measured = Scores.model_validate_json(path.read_text("utf-8"))
            if model in measured.models:
                return measured.models[model].cost_per_trial_usd
    return None


async def run(
    cases: list[Case], models: list[str], trials: int, max_cost_usd: float, concurrency: int, variant: str
) -> Path:
    out = RUNS / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True)
    records: list[TrialRecord] = []
    errors = 0
    spent = 0.0
    stopped_at_cap = False
    limit = anyio.Semaphore(concurrency)
    claude = anthropic.AsyncAnthropic()

    def write(name: str, line: str) -> None:
        with (out / name).open("a", encoding="utf-8") as file:
            file.write(line + "\n")

    async def one(case: Case, model: str, number: int) -> None:
        nonlocal errors, spent, stopped_at_cap
        async with limit:
            if spent >= max_cost_usd:
                stopped_at_cap = True
                return
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    record = await run_trial(claude, case, model, variant)
                except WrongModelError:
                    raise
                except Exception as error:  # noqa: BLE001 - API errors, timeouts and crashes are logged, not scored
                    errors += 1
                    # The type and status only: an error's message or request could carry headers.
                    status = getattr(error, "status_code", None)
                    write(
                        "errors.jsonl",
                        json.dumps(
                            {
                                "case_id": case.id,
                                "model": model,
                                "trial": number,
                                "attempt": attempt,
                                "error": type(error).__name__,
                                "status": status,
                            }
                        ),
                    )
                    continue
                records.append(record)
                spent += trial_cost_usd(model, record.usage)
                write("trials.jsonl", record.model_dump_json())
                print(f"{case.id} {model} #{number}: {'pass' if record.passed else 'FAIL'}", flush=True)
                return

    async with anyio.create_task_group() as group:
        for case in cases:
            for model in models:
                for number in range(1, trials + 1):
                    group.start_soon(one, case, model, number)

    # Trials finish in any order. Report them in case order, then model order.
    case_order = [case.id for case in cases]
    records.sort(key=lambda record: (case_order.index(record.case_id), models.index(record.model)))
    on = ", ".join(f"{model} (effort {EFFORT[model]})" for model in models)
    header = [
        f"# Eval run {out.name}",
        "",
        f"{len(cases)} cases, {trials} trials each, on {on}, with the `{variant}` tools.",
        "",
    ]
    if stopped_at_cap:
        header += [f"Stopped starting trials at the ${max_cost_usd:.2f} cost cap, so some trials didn't run.", ""]
    run_scores = scores(records)
    (out / "scores.json").write_text(run_scores.model_dump_json(indent=2), encoding="utf-8")
    parts = [*header, render_summary(records, errors=errors)]
    if BASELINE.exists() and records:
        parts.append(render_comparison(Scores.model_validate_json(BASELINE.read_text("utf-8")), run_scores))
    (out / "summary.md").write_text("\n".join(parts), encoding="utf-8")
    return out


def estimate(cases: list[Case], models: list[str], trials: int) -> float | None:
    cost_per_trial = {model: measured_cost_per_trial(model) for model in models}
    for model, per_trial in cost_per_trial.items():
        count = len(cases) * trials
        if per_trial is None:
            print(f"{model}: {count} trials. No earlier run to estimate the cost from.")
        else:
            print(f"{model}: {count} trials, about ${per_trial * count:.2f} (${per_trial:.4f} per trial).")
    return estimate_usd(cases=len(cases), trials=trials, cost_per_trial=cost_per_trial)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m evals", description="Run the tool-use evals. See docs/evals.md.")
    parser.add_argument("--models", nargs="+", choices=list(EFFORT), default=["claude-sonnet-5-5"])
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument(
        "--cases", nargs="+", default=["*"], help="names or globs over evals/cases/*.yaml, without .yaml"
    )
    parser.add_argument("--variant", choices=list(VARIANTS), default="current", help="the set of tools to give Claude")
    parser.add_argument("--max-cost-usd", type=float, required=True, help="stop starting trials once this is spent")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        sys.exit(f"No cases match {', '.join(f'evals/cases/{pattern}.yaml' for pattern in args.cases)}")
    print(f"{len(cases)} cases, with the {args.variant} tools.")
    expected = estimate(cases, args.models, args.trials)
    if expected is not None and expected > args.max_cost_usd:
        sys.exit(f"Not running: the estimate, ${expected:.2f}, is over --max-cost-usd ${args.max_cost_usd:.2f}.")
    out = anyio.run(run, cases, args.models, args.trials, args.max_cost_usd, args.concurrency, args.variant)
    print(f"\nResults: {out}\n")
    print((out / "summary.md").read_text("utf-8"))
