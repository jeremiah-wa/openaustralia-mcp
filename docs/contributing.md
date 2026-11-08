# Contributing

Conventions and house rules for this repo. They apply equally to people and to coding agents.

## House rules

These protect users' keys and keep the project within the data licences. Don't break them, even temporarily.

1. **Never commit an API key.**
   - The server's keys come only from `OPENAUSTRALIA_API_KEY` and `THEYVOTEFORYOU_API_KEY`.
   - The evals' key comes only from `ANTHROPIC_API_KEY`. The server never reads it.
   - `.env` stays gitignored, and `.env.example` holds placeholders only.
2. **Scrub keys from recorded responses.**
   - Test fixtures are recorded from live calls, and the request URL contains `key=…`.
   - Remove the key before committing a fixture.
   - Check with `git diff --staged` before every commit that adds or changes fixtures.
   - Run `uv run pre-commit install` once per clone. A pre-commit hook then runs [gitleaks](https://github.com/gitleaks/gitleaks) on what's staged, using the rule in [.gitleaks.toml](../.gitleaks.toml), and blocks a commit that contains a key. Don't bypass it with `--no-verify`.
   - CI scans the commits each pull request and each push to `main` adds, with the same rule, and fails if it finds a key. Both are backstops, not a reason to skip the check.
3. **Keys never appear in logs, tool results, error messages or eval results.**
4. **Read-only.** No tool changes data anywhere.
5. **Cut Hansard text, never rewrite it.**
   - Hansard is CC BY-NC-ND (no derivatives). The server may cut, excerpt and paginate it, but must not paraphrase or summarise it. Summarising is left to the client model, which is an assumption (see [ADR 0003](adr/0003-cut-hansard-never-rewrite-it.md)).
6. **Every tool result carries attribution:** a source URL and the licence line for its data.
7. **Non-commercial.** Don't add anything that charges for access or resells the data.
8. **Keep results small.**
   - Don't return a raw API response from a tool.
   - New tools follow the result-shaping rules in [tools.md](tools.md#result-shaping).

## Design changes

- [architecture.md](architecture.md) and [tools.md](tools.md) record the current design and the reasons for it. If a change goes against something in them (tool names, result sizes, caching), update the doc in the same change.
- [api-notes.md](api-notes.md) records what the APIs actually do. Add what a live call shows there.
- [adr/](adr/) records the big decisions, one file each. Add one only when a decision is all three of: hard to reverse, surprising without context, and the result of a real trade-off. Smaller decisions go in the doc they affect, with the reason.
  - Name it `NNNN-slug.md`, with the next number. One paragraph is usually enough: the context, the decision and why. Add `Considered options` only when the rejected alternatives are worth remembering.
  - When a decision changes, don't rewrite its ADR. Add a new one, and give the old one `status: superseded by ADR-NNNN` in frontmatter.
- Tool names and descriptions are written for the model. When you rename a tool or change its description, check that the server `instructions` still describe the right chain of calls.

## Adding a tool

1. Check [api-notes.md](api-notes.md) for what the API does. Make live calls for anything it doesn't cover, and add what they show.
2. Record the responses the tests need (see [Recording a response](#recording-a-response)).
3. Build it test-first, in small commits (see [Tests](#tests)), keeping to the [house rules](#house-rules).
   - Put the tool and its result models in its family's module in `src/openaustralia_mcp/tools/`: `members.py` for members, `hansard.py` for Hansard. A new family, such as the They Vote For You tools, gets its own module, with a `register` function that adds its tools to the server. Call it from `build_server`, in the order the tools should be listed.
   - Every tool uses `READ_ONLY` and `_describe`, from `tools/__init__.py`.
   - The result model's `from_…` constructor sets `source_url` and `licence`, for the API the data comes from.
4. Add the tool to the server `instructions` in `server.py`, so Claude knows where it fits in the chain of calls.
5. Add eval cases, and put the scores before and after in the pull request (see [Evals](#evals)).
6. Set the tool's status in [tools.md](tools.md), and record any naming or shaping decision there. Add an ADR if one qualifies (see [Design changes](#design-changes)).

## Recording a response

A fixture holds only the response body, as the API sent it, under `tests/fixtures/openaustralia/`. Name it after the function and its parameters, e.g. `getHansard_search_housing_person_10887.json`. OpenAustralia is a free service run by a charity, so record only what the tests need.

To record one, set the first three values and run this in bash from the repo root, with your key in `.env`:

```bash
uv run --env-file .env python - <<'EOF'
import os
from pathlib import Path

import httpx2

function = "getRepresentatives"
params = {"postcode": "3056"}
fixture = "getRepresentatives_postcode_3056.json"

response = httpx2.get(
    f"https://www.openaustralia.org.au/api/{function}",
    params={"key": os.environ["OPENAUSTRALIA_API_KEY"], "output": "js", **params},
    timeout=20,
)
Path("tests/fixtures/openaustralia", fixture).write_bytes(response.content)
print(response.status_code)
EOF
```

Then add the request to `RECORDED` (see [Tests](#tests)), and check the diff for a key (see [House rules](#house-rules)).

## Code

- Python, managed with `uv`. Add dependencies with `uv add`, not by editing `pyproject.toml` by hand.
- Format and lint with `ruff` (`uv run ruff format` and `uv run ruff check`).
- Type-hint public functions.
- API clients don't import anything from MCP, and tools don't build HTTP requests themselves (see [architecture.md](architecture.md#components)).

## Tests

- **Write the test first.** Write one failing test for the next behaviour, run it to see it fail, then write only the code that makes it pass. Repeat for each behaviour. Don't write the code first and then add tests that fit it.
- Test through the MCP tool call, using the in-memory client and recorded responses. Don't test internal functions directly. That's what lets the internals change when tools are reworked around tasks.
- Take expected values from an independent source, such as a recorded response or the API docs. Never work them out the same way the code does.
- When you record a response, add the request it answers to `RECORDED` in [tests/fake_api.py](../tests/fake_api.py), and serve it with `fake_api.route(...)`. Use `serve_fixture` only for error responses that would answer any request. To give one request a response that can't be recorded, such as an HTTP 502 among recorded responses, use `fake_api.answer(...)` rather than a handler of the test's own.
- Group related tests in classes named after the behaviour, e.g. `TestMissingKey` and `TestKeyNeverLeaks`.
- Every new tool gets a row in `EVERY_CALL`, in [tests/test_every_tool.py](../tests/test_every_tool.py), and the recorded responses that answer it go in `EVERY_ANSWER`. That file checks what every tool must do: explain a missing or rejected key, pass on an API error with its arguments, say when OpenAustralia is unavailable, and never leak the key (`TestKeyNeverLeaks`). A test fails if the server lists a tool that has no row. The tool's own test file covers its normal result and anything else only it does.
- `uv run pytest` must pass before you commit. CI ([ci.yml](../.github/workflows/ci.yml)) also runs it, with ruff, on every pull request and every push to `main`. Live smoke tests run only when the key env vars are set. In CI they run only in [live.yml](../.github/workflows/live.yml), weekly, by hand and on pull requests that change them, with the key from the `OPENAUSTRALIA_API_KEY` repository secret. Don't add a live call to any other workflow.

## Evals

The evals measure whether Claude picks the right tool with the right arguments. See [evals.md](evals.md).

- Every change to a tool's name, description or arguments, or to the server `instructions`, adds or updates eval cases. Put the scores before and after the change in the pull request. Add the `run-evals` label to run them in CI. The job summary compares the run with the baseline.
- When such a change merges, update the baseline from a full run: copy its `summary.md` to `evals/results/baseline.md` (keeping the notes at the top up to date) and its `scores.json` to `evals/results/baseline.json`.
- Evals call the Anthropic API, so they cost money and aren't deterministic. They never run under `uv run pytest` or in [ci.yml](../.github/workflows/ci.yml), which keeps the Anthropic key out of the jobs that run on every push. In CI they run only in [evals.yml](../.github/workflows/evals.yml): by hand, or when a pull request gets the `run-evals` label, never on a push. To run them again on a pull request, remove the label and add it back. The key comes from the `ANTHROPIC_API_KEY` repository secret, and reaches only the steps that check it and run them. Don't add an eval run to any other workflow.
- Every run needs `--max-cost-usd` (see [Cost](evals.md#cost)). The scores don't fail the job yet. A threshold can come once there are a few runs to compare.
- The eval's own logic, such as the case format and the graders, is tested directly in `tests/test_eval_*.py`. Those tests are free and deterministic, so they do run under `uv run pytest` and in CI.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <summary in the imperative, lower case, no full stop>

<optional body: what changed and why, wrapped at 72 characters>
```

| Type | Use for |
|---|---|
| `feat` | A new tool or a change in behaviour users can see |
| `fix` | A bug fix |
| `docs` | README, anything under `docs/`, or tool descriptions only |
| `test` | Tests or fixtures only |
| `refactor` | Code changes with no change in behaviour |
| `chore` | Dependencies, tooling, CI |

Scopes, where one helps: `oa` (OpenAustralia client), `tvfy` (They Vote For You client), `tools`, `cache`, `server`, `evals`.

Examples:

```
feat(tools): add search_hansard with excerpt trimming
fix(cache): stop caching responses that contain an API error
docs: record person_id check result in api-notes.md
```

- Keep each commit on a branch to one logical change, so the pull request can be reviewed a step at a time. A tool is usually several commits: one per behaviour, each with its test and the code that makes it pass, e.g. "add get_members lookup by postcode", then "explain a missing OpenAustralia key".
- Code, its tests and any doc updates for it go in the same commit.
- Mark breaking changes to a tool's name or arguments with `!` (e.g. `feat(tools)!: rename get_members query argument`) and explain the change in the body. A pull request with a breaking change carries the `!` in its title too, because the title becomes the commit on `main`.

## Branches and pull requests

- `main` is always in a working state. Do your work on a short-lived branch named `<type>/<short-description>`, e.g. `feat/search-hansard`.
- Open a pull request into `main`. The description says what changed and why, and how you tested it, including any manual checks in MCP Inspector or Claude Desktop.
- Squash-merge into `main`, so each pull request is one commit there. Some pull requests have dozens of commits, which would make `main`'s history noisy. So a pull request is what gets reverted, not a commit within it: keep each pull request to one change, which could be reverted without losing other work. The repository allows only squash-merging, and deletes a branch once its pull request is merged.
- The pull request's title becomes that commit's summary, so write it as a commit summary (see [Commits](#commits)), with the type of its most significant change: a tool built with `test` and `feat` commits is `feat`. The branch's commit messages become the commit's body.
- A branch made from another branch has to be rebased once the first is squash-merged, because its commits are no longer on `main`: `git rebase --onto main <first branch> <your branch>`, then force-push it.

## Labels

- The labels are listed in [.github/labels.yml](../.github/labels.yml). Add, change or remove a label there, not on GitHub: when the file changes on `main`, the [Labels workflow](../.github/workflows/labels.yml) makes GitHub's labels match it, and deletes any that aren't listed. A label made on GitHub instead is deleted at the next sync.
- A pull request that changes the file shows what will change in the Labels job's summary. Check it before merging, especially for deletions: deleting a label takes it off every issue and pull request, and recreating it doesn't put it back.
- The workflow won't delete a label that's still on an issue or a pull request, and fails instead. Take the label off them first, or keep it in the file.
- To rename a label, change its name in the file and list the old name in `renamed_from`, so its issues keep it. Once the rename is on `main`, `renamed_from` can go.
- Give each issue one kind (`bug`, `feature`, `refactor`, `documentation`, `chore` or `research`), and one priority when it's planned: `priority: high` for what's next or blocks the next stage of the [roadmap](../README.md#roadmap), `priority: medium` for what's planned after that, and `priority: low` for what can wait until someone next works in that area.
- `research` is for an issue whose result is a decision rather than code: an experiment, a measurement, a design or an investigation, such as #8 or #17. Code it leads to gets its own issue, of its own kind.
- `run-evals` runs the evals on a pull request (see [Evals](#evals)). Don't rename it: [evals.yml](../.github/workflows/evals.yml) matches it by name.
