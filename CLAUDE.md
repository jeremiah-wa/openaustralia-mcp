# OpenAustralia MCP server

A learning side project: a local MCP server, written in Python, that lets Claude answer questions about the federal Australian Parliament (members, electorates, Hansard, votes). It is a thin layer over the OpenAustralia and They Vote For You APIs, which are both run by the OpenAustralia Foundation. The goal is to learn how MCP servers and Claude connectors work. Each user brings their own API keys.

The project is in early building. [tools.md](docs/tools.md) says which tools work so far.

## Docs

- [README.md](README.md): what the server does, its tools, setup for Claude Desktop and Claude Code, data licences, development commands, roadmap.
- [architecture.md](docs/architecture.md): components, tool-to-API mapping, key and error handling, result shaping, caching, testing seams, decision log, open questions.
- [contributing.md](docs/contributing.md): house rules (keys, licences, read-only), code and test conventions, commit and branch conventions.
- [evals.md](docs/evals.md): evals of Claude's tool use: seam, runner, cases, graders, trials, models, results, cost.

Read architecture.md before changing tools, result sizes, caching or tests, and evals.md before changing a tool's name, description or arguments. When a design decision changes, update those docs, not this file.

Follow the commit conventions in contributing.md. Never add a `Co-Authored-By: Claude` trailer, or any other AI attribution, to commits or pull requests.
