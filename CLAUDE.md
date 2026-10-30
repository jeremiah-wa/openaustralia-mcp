# OpenAustralia MCP server

A learning side project: a local MCP server, written in Python, that lets Claude answer questions about the federal Australian Parliament (members, electorates, Hansard, votes). It is a thin layer over the OpenAustralia and They Vote For You APIs, which are both run by the OpenAustralia Foundation. The goal is to learn how MCP servers and Claude connectors work. Each user brings their own API keys.

The project is in early building. [tools.md](docs/tools.md) says which tools work so far.

## Docs

- [README.md](README.md): what the server does, its tools, setup for Claude Desktop and Claude Code, data licences, development commands, roadmap.
- [architecture.md](docs/architecture.md): components, request flow, key and error handling, testing seams, stack, open questions, later stages.
- [tools.md](docs/tools.md): each tool's status and API calls, naming, result shaping, caching.
- [api-notes.md](docs/api-notes.md): what live calls have shown each API actually does.
- [adr/](docs/adr/): the big decisions and why they went that way, one file each.
- [contributing.md](docs/contributing.md): house rules (keys, licences, read-only), steps for adding a tool or recording a response, code and test conventions, commit and branch conventions.
- [evals.md](docs/evals.md): evals of Claude's tool use: seam, runner, cases, graders, trials, models, results, cost.

Read tools.md and api-notes.md before changing tools, result sizes or caching, architecture.md before changing tests or how the server is built, and evals.md before changing a tool's name, description or arguments. When a design decision changes, update those docs, not this file.

Follow the commit conventions in contributing.md. Never add a `Co-Authored-By: Claude` trailer, or any other AI attribution, to commits or pull requests.
