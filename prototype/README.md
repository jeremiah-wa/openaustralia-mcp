# PROTOTYPE: module-level tools, with the client injected by `Resolve`

Throwaway, on the `chore/resolve-prototype` branch only. Not for `main`.

## The question

Can the tools be plain module-level functions, as in the `mcp` SDK's tutorials, while every server that `build_server` makes keeps its own API client? It has to keep what Claude sees (`list_tools()` and the instructions) byte-identical to `main`, and the tests have to pass unchanged. It follows on from the split into a module per tool family (#27).

The design, in `src/openaustralia_mcp/`:

- `tools/__init__.py`: a `ToolSet` per family collects its tools when the module is imported, and `add_to(server)` adds them with `READ_ONLY`. A tool parameter typed `OpenAustralia` (`Annotated[OpenAustraliaClient, Resolve(...)]`) gets its server's client, read from the lifespan context. The SDK leaves it out of the input schema.
- `server.py`: `build_server` gives each server a lifespan that yields its own `Clients`, then adds each family's tools in order.
- `tools/members.py`, `tools/hansard.py`: the tool functions are at module level, under `@tools.tool`, with the client as their first parameter. Their bodies haven't changed.

## Running the checks

From the repo root:

```bash
uv run pytest                                 # the tests, unchanged
uv run python prototype/dump_tools.py x.json  # what Claude sees, to diff against the same run on main
uv run python prototype/isolation_check.py    # two servers at once, each with its own fake API
uv run python prototype/paths_check.py        # every tool in both in-process modes, and over stdio
uv run python prototype/compare_cleandoc.py a.json b.json  # compare two snapshots, ignoring docstring indentation
```

## The answer

**Yes, on Python 3.13**, which is the project's `.python-version` and what CI and the evals run on:

- `list_tools()` and the instructions are byte-identical to `main`.
- The 282 tests pass unchanged (16 live tests skipped).
- Two servers called at the same time, over 20 interleaved rounds, each used only their own client.
- All three tools work in both of the in-process `Client`'s modes, `auto` (the modern per-request path, which the tests use) and `legacy` (the stream loop). Over stdio, the real entry point lists the tools in order, and `get_members` goes through the lifespan and the resolver to the client.

**Python 3.12 changes the descriptions' whitespace.** `pyproject.toml` allows 3.12. A tool's description is its function's raw docstring, and 3.12 doesn't strip a docstring's indentation (3.13 does). Moving the functions to module level takes the indentation inside each description from 8 spaces to 4. On `main`, 3.12 and 3.13 already give different descriptions (8 spaces against none), so what Claude sees already depends on the Python version. That's worth an issue of its own. `ToolSet.add_to` would be one place to fix it, by passing each description through `inspect.cleandoc`.

Not checked: a manual run in MCP Inspector or Claude Desktop, and clients that negotiate older protocol versions, beyond the `legacy` mode.
