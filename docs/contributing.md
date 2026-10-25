# Contributing

Conventions and house rules for this repo. They apply equally to people and to coding agents.

## House rules

These protect users' keys and keep the project within the data licences. Don't break them, even temporarily.

1. **Never commit an API key.**
   - Keys come only from `OPENAUSTRALIA_API_KEY` and `THEYVOTEFORYOU_API_KEY`.
   - `.env` stays gitignored, and `.env.example` holds placeholders only.
2. **Scrub keys from recorded responses.**
   - Test fixtures are recorded from live calls, and the request URL contains `key=…`.
   - Remove the key before committing a fixture.
   - Check with `git diff --staged` before every commit that adds or changes fixtures.
3. **Keys never appear in logs, tool results or error messages.**
4. **Read-only.** No tool changes data anywhere.
5. **Cut Hansard text, never rewrite it.**
   - Hansard is CC BY-NC-ND (no derivatives). The server may cut, excerpt and paginate it, but must not paraphrase or summarise it. Summarising is the client model's job.
6. **Every tool result carries attribution:** a source URL and the licence line for its data.
7. **Non-commercial.** Don't add anything that charges for access or resells the data.
8. **Keep results small.**
   - Don't return a raw API response from a tool.
   - New tools follow the result-shaping rules in [architecture.md](architecture.md#result-shaping).

## Design changes

- [architecture.md](architecture.md) records the current design and the reasons for it. If a change goes against something in it (tool names, result sizes, caching, the one-server decision), update the doc in the same change and add a row to its decision table.
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
- Group related tests in classes named after the behaviour, e.g. `TestMissingKey` and `TestKeyNeverLeaks`.
- Every new tool gets a test for its normal result, for a missing key, for an API error and for never leaking the key (`TestKeyNeverLeaks`).
- `uv run pytest` must pass before you commit. CI ([ci.yml](../.github/workflows/ci.yml)) also runs it, with ruff, on every pull request and every push to `main`. Live smoke tests run only when the key env vars are set, and they never run in CI.

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
| `docs` | README, architecture.md, this file, or tool descriptions only |
| `test` | Tests or fixtures only |
| `refactor` | Code changes with no change in behaviour |
| `chore` | Dependencies, tooling, CI |

Scopes, where one helps: `oa` (OpenAustralia client), `tvfy` (They Vote For You client), `tools`, `cache`, `server`.

Examples:

```
feat(tools): add search_hansard with excerpt trimming
fix(cache): stop caching responses that contain an API error
docs: record person_id check result in architecture.md
```

- Keep each commit to one logical change, small enough to revert without losing other work. A tool is usually several commits: one per behaviour, each with its test and the code that makes it pass, e.g. "add get_members lookup by postcode", then "explain a missing OpenAustralia key".
- Code, its tests and any doc updates for it go in the same commit.
- Mark breaking changes to a tool's name or arguments with `!` (e.g. `feat(tools)!: rename get_members query argument`) and explain the change in the body.

## Branches and pull requests

- `main` is always in a working state. Do your work on a short-lived branch named `<type>/<short-description>`, e.g. `feat/search-hansard`.
- Open a pull request into `main`. The description says what changed and why, and how you tested it, including any manual checks in MCP Inspector or Claude Desktop.
- Squash-merge, using a Conventional Commit title for the squashed commit.
