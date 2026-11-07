# PROTOTYPE: module-level tools that read the client from the lifespan

Throwaway, on the `chore/context-prototype` branch only. Not for `main`.

## The question

#33 wants the tools as plain module-level functions, as in the `mcp` SDK's tutorials, while every server that `build_server` makes keeps its own API client. This is option 2 for it, the pattern from the SDK's [Lifespan docs](https://py.sdk.modelcontextprotocol.io/handlers/lifespan/): the lifespan yields the server's clients, and each tool reads them through a typed `Context`. Option 3, injecting the client with `Resolve`, was prototyped on `chore/resolve-prototype`.

Does option 2 keep what Claude sees (`list_tools()` and the instructions) byte-identical to `main`, with the tests unchanged? Does each server keep its own client, on every way of connecting? Is the client typed, as the docs say? And how does it compare with option 3?

The design, in `src/openaustralia_mcp/`:

- `tools/__init__.py`: `Clients`, a dataclass with a field for each API client, and a `ToolSet` per family, which collects its tools when the module is imported. `add_to(server)` adds them with `READ_ONLY`.
- `server.py`: `build_server` gives each server a lifespan that yields its own `Clients`, then adds each family's tools in order.
- `tools/members.py`, `tools/hansard.py`: the tool functions are at module level, under `@tools.tool`. Each takes `ctx: Context[Clients]` as its first parameter, and starts with `openaustralia = ctx.request_context.lifespan_context.openaustralia`. Otherwise their bodies haven't changed. `ctx` comes first because every argument of `get_members` has a default.

Against option 3, each tool trades its `openaustralia: OpenAustralia` parameter for the `Context` and gains that one line, and the resolver and the `OpenAustralia` type go: `git diff chore/resolve-prototype chore/context-prototype -- src`.

## Running the checks

From the repo root:

```bash
uv run pytest                                 # the tests, unchanged
uv run python prototype/dump_tools.py x.json  # what Claude sees, to diff against the same run on main
uv run python prototype/isolation_check.py    # two servers at once, each with its own fake API
uv run python prototype/paths_check.py        # every tool in both in-process modes, and over stdio
uv run python prototype/wire_check.py x.json  # every tool call's full result, to diff against another branch's
MYPYPATH=src uv run --with mypy mypy --follow-imports=silent prototype/type_check.py  # what a type checker sees
```

## The answer

**Yes, on every check:**

- `list_tools()` and the instructions are byte-identical to `main`, and the 282 tests pass unchanged (16 live tests skipped).
- Two servers called at the same time, over 20 interleaved rounds, each used only their own client.
- All three tools work in both of the in-process `Client`'s modes, `auto` and `legacy`. Over stdio, the real entry point lists the tools in order, and `get_members` reaches the client through the lifespan.
- The client is typed, as the docs say. mypy reveals `OpenAustraliaClient` for `ctx.request_context.lifespan_context.openaustralia`, and reports a misspelt attribute ("maybe "openaustralia"?"). The project runs no type checker in CI, so day to day that help shows up in the editor.

**Against option 3:**

- Every `tools/call` result, `_meta` included, is byte-identical between the two prototypes: all 10 calls, in both modes, including an API error and a `ToolError`. The SDK docs call a tool with a `Resolve` parameter "a multi-round-trip tool", but a resolver that never asks a question makes no round trip, so nothing a client receives changes.
- So they differ only in their code: one line per tool here, against a resolver and an `Annotated` type there.

Not checked: a manual run in MCP Inspector or Claude Desktop, and the HTTP transports.
