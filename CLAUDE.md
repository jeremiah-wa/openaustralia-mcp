# OpenAustralia MCP server

A learning side project: a local MCP server, written in Python, that lets Claude answer questions about the federal Australian Parliament (members, electorates, Hansard, votes). It is a thin layer over the OpenAustralia and They Vote For You APIs, which are both run by the OpenAustralia Foundation. The goal is to learn how MCP servers and Claude connectors work. Each user brings their own API keys.

The project is at the start of building. The uv package skeleton and console script exist, but no tools have been built yet.

## Docs

- [README.md](README.md): what the server does, its tools, setup for Claude Desktop and Claude Code, data licences, development commands, roadmap.
- [architecture.md](docs/architecture.md): components, tool-to-API mapping, key and error handling, result shaping, caching, testing seams, decision log, open questions.
- [contributing.md](docs/contributing.md): house rules (keys, licences, read-only), code and test conventions, commit and branch conventions.

Read architecture.md before changing tools, result sizes, caching or tests. When a design decision changes, update those docs, not this file.

Follow the commit conventions in contributing.md. Never add a `Co-Authored-By: Claude` trailer, or any other AI attribution, to commits or pull requests.
