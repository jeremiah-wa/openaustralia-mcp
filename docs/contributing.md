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
   - CI scans every commit with the same rule and fails if it finds a key. Both are backstops, not a reason to skip the check.
3. **Keys never appear in logs, tool results, error messages or eval results.**
4. **Read-only.** No tool changes data anywhere.
5. **Cut Hansard text, never rewrite it.**
   - Hansard is CC BY-NC-ND (no derivatives). The server may cut, excerpt and paginate it, but must not paraphrase or summarise it. Summarising is the client model's job.
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

## Code

- Python, managed with `uv`. Add dependencies with `uv add`, not by editing `pyproject.toml` by hand.
- Format and lint with `ruff` (`uv run ruff format` and `uv run ruff check`).
- Type-hint public functions.
- API clients don't import anything from MCP, and tools don't build HTTP requests themselves (see [architecture.md](architecture.md#components)).

## Tests

- **Write the test first.** Write one failing test for the next behaviour, run it to see it fail, then write only the code that makes it pass. Repeat for each behaviour. Don't write the code first and then add tests that fit it.
- Test through the MCP tool call, using the in-memory client and recorded responses. Don't test internal functions directly. That's what lets the internals change when tools are reworked around tasks.
- Take expected values from an independent source, such as a recorded response or the API docs. Never work them out the same way the code does.
- When you record a response, add the request it answers to `RECORDED` in [tests/fake_api.py](../tests/fake_api.py), and serve it with `fake_api.route(...)`. Use `serve_fixture` only for error responses that would answer any request.
- Group related tests in classes named after the behaviour, e.g. `TestMissingKey` and `TestKeyNeverLeaks`.
- Every new tool gets a test for its normal result, for a missing key, for an API error and for never leaking the key (`TestKeyNeverLeaks`).
- `uv run pytest` must pass before you commit. CI ([ci.yml](../.github/workflows/ci.yml)) also runs it, with ruff, on every pull request and every push to `main`. Live smoke tests run only when the key env vars are set. In CI they run only in [live.yml](../.github/workflows/live.yml), weekly, by hand and on pull requests that change them, with the key from the `OPENAUSTRALIA_API_KEY` repository secret. Don't add a live call to any other workflow.

## Evals

The evals measure whether Claude picks the right tool with the right arguments. See [evals.md](evals.md).

- Every change to a tool's name, description or arguments, or to the server `instructions`, adds or updates eval cases. Put the scores before and after the change in the pull request. Add the `run-evals` label to run them in CI. The job summary compares the run with the baseline.
- When such a change merges, update the baseline from a full run: copy its `summary.md` to `evals/results/baseline.md` (keeping the notes at the top up to date) and its `scores.json` to `evals/results/baseline.json`.
- Evals call the Anthropic API, so they cost money and aren't deterministic. They never run in [ci.yml](../.github/workflows/ci.yml) or under `uv run pytest`. In CI they run only in [evals.yml](../.github/workflows/evals.yml): by hand, or when a pull request gets the `run-evals` label, never on a push. To run them again on a pull request, remove the label and add it back. The key comes from the `ANTHROPIC_API_KEY` repository secret, and reaches only the steps that check it and run them. Don't add an eval run to any other workflow.
- Every run needs `--max-cost-usd`. The runner refuses a run whose estimate is over it, and stops starting trials once it's spent. The scores don't fail the job yet. A threshold can come once there are a few runs to compare.
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

- Keep each commit to one logical change, small enough to revert without losing other work. A tool is usually several commits: one per behaviour, each with its test and the code that makes it pass, e.g. "add get_members lookup by postcode", then "explain a missing OpenAustralia key".
- Code, its tests and any doc updates for it go in the same commit.
- Mark breaking changes to a tool's name or arguments with `!` (e.g. `feat(tools)!: rename get_members query argument`) and explain the change in the body.

## Branches and pull requests

- `main` is always in a working state. Do your work on a short-lived branch named `<type>/<short-description>`, e.g. `feat/search-hansard`.
- Open a pull request into `main`. The description says what changed and why, and how you tested it, including any manual checks in MCP Inspector or Claude Desktop.
- Squash-merge, using a Conventional Commit title for the squashed commit.
