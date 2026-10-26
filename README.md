# openaustralia-mcp

An MCP server that lets Claude (and other MCP clients) answer questions about the federal Australian Parliament: who represents an electorate, what members have said in Hansard, and how they vote.

It is a thin layer over two existing APIs run by the [OpenAustralia Foundation](https://www.openaustralia.org.au/):

- **[OpenAustralia](https://www.openaustralia.org.au/api/)**: members, electorates, Hansard and debates.
- **[They Vote For You](https://theyvoteforyou.org.au/)**: votes in Parliament (divisions) and policy positions.

> **Status: early build.** This README describes the planned first release. So far `get_members` (Representatives by postcode), `search_hansard` and `read_debate` work. The other tools haven't been built yet.

## What you can ask

Once it's connected, you can ask Claude things like:

- "Who is my federal MP for postcode 3056?"
- "What has my local member said about housing this year?"
- "Find Senate debates on the NDIS from last month and summarise the main arguments."
- "How does Senator X vote on increasing housing affordability?"

Claude picks the tools, chains them (find the member → search Hansard → read the debate) and cites the source for each result.

## Tools

| Tool | Source | What it does |
|---|---|---|
| `get_members` | OpenAustralia | Find Representatives and Senators by name, postcode or party. Returns `person_id`s. |
| `get_electorates` | OpenAustralia | Look up electorates (OpenAustralia calls them "divisions") by name or postcode. |
| `search_hansard` | OpenAustralia | Search what was said in Parliament. Returns short excerpts with a `gid` per hit. |
| `read_debate` | OpenAustralia | Read the full text of a speech, or a whole debate, by `gid` and house, a page at a time. |
| `get_policies` / `get_policy` | They Vote For You | Policy topics and how each member's votes line up with them. |
| `get_votes` / `get_vote` | They Vote For You | Individual votes in Parliament (divisions) and how each member voted. |

All tools are read-only.

## Requirements

### To use the server

| You need | Why | How to get it |
|---|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Installs and runs the server. You don't need to install Python yourself: uv downloads a suitable version (3.12 or later) the first time. | macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh`<br>Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| [Git](https://git-scm.com/downloads) | uv fetches the server straight from this repository. | Already installed on most developer machines. Check with `git --version`. |
| An MCP client | Runs the server and talks to it. | [Claude Desktop](https://claude.ai/download), Claude Code, or another client that supports local (stdio) servers |
| An OpenAustralia API key | Used by the member, electorate and Hansard tools | <https://www.openaustralia.org.au/api/key>. Free for low-volume, non-commercial use. |
| A They Vote For You API key | Used by the voting and policy tools | Sign in at <https://theyvoteforyou.org.au/>. |

The server starts without either key. Each tool needs only its own key: if that key is missing or rejected, the tool returns a message saying so and linking to where to get one, and the other tools keep working. So you can start with just the OpenAustralia key and add the other later.

### For development

All of the above, plus:

- [Node.js](https://nodejs.org/) 22.19 or later, only if you want to use MCP Inspector (see [Development](#development)).

Keys are optional here too. The unit tests run against recorded responses.

## Setup

### Claude Desktop

Add this to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "openaustralia": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/jeremiah-wa/openaustralia-mcp",
        "openaustralia-mcp"
      ],
      "env": {
        "OPENAUSTRALIA_API_KEY": "your-openaustralia-key",
        "THEYVOTEFORYOU_API_KEY": "your-theyvoteforyou-key"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

### Claude Code

```bash
claude mcp add openaustralia -e OPENAUSTRALIA_API_KEY=your-openaustralia-key -e THEYVOTEFORYOU_API_KEY=your-theyvoteforyou-key -- uvx --from git+https://github.com/jeremiah-wa/openaustralia-mcp openaustralia-mcp
```

### Other MCP clients

Any client that runs local (stdio) MCP servers can use the same command, arguments and environment variables.

## Data and licences

The code in this repository is MIT licensed. The data it fetches is not, and the server keeps to the terms below:

| Data | Owner | Licence |
|---|---|---|
| Hansard (`search_hansard`, `read_debate`) | Commonwealth of Australia | [CC BY-NC-ND 3.0 AU](https://creativecommons.org/licenses/by-nc-nd/3.0/au/) |
| Members, electorates | OpenAustralia Foundation | [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5/) |
| Votes, policies | They Vote For You | See [their data page](https://theyvoteforyou.org.au/help/data) |

Specifically:

- Hansard text is shortened but never rewritten, and every result includes a source link and attribution.
- Use of the APIs is free for low-volume, non-commercial use. Every user brings their own keys, which keeps usage spread out. Contact OpenAustralia before any commercial or large-scale use.

If you fork this project, these terms apply to you too.

## Development

```bash
git clone https://github.com/jeremiah-wa/openaustralia-mcp
cd openaustralia-mcp
uv sync
uv run pre-commit install   # blocks commits that contain an API key
uv run pytest
```

- Unit tests run against recorded API responses and don't need a key.
- Set `OPENAUSTRALIA_API_KEY` (and optionally `THEYVOTEFORYOU_API_KEY`) to also run the live smoke tests. CI runs them weekly against the real API.
- To poke at the tools by hand, use [MCP Inspector](https://github.com/modelcontextprotocol/inspector) v2 (needs Node 22.19 or later). Keep `@latest` in the command, or npx may run an old cached v1:

```bash
# Web UI
npx @modelcontextprotocol/inspector@latest uv run openaustralia-mcp

# CLI, e.g. to list the tools
npx @modelcontextprotocol/inspector@latest --cli --method tools/list uv run openaustralia-mcp
```

Copy `.env.example` to `.env` to keep keys out of your shell history. `.env` is gitignored. Load it with `--env-file`:

```bash
uv run --env-file .env pytest                       # includes the live smoke tests
npx @modelcontextprotocol/inspector@latest uv run --env-file .env openaustralia-mcp
```

See [architecture.md](docs/architecture.md) for how the server is put together.

### Running the evals

The evals check that Claude picks the right tool with the right arguments. They call the Anthropic API, so they cost money, and they never run under `uv run pytest` or in CI. Put `ANTHROPIC_API_KEY` in `.env`, then:

```bash
# One case, one trial, on Haiku: well under a cent
uv run --group evals --env-file .env python -m evals --models claude-haiku-5-5 --trials 1 --cases mp-3056 --max-cost-usd 0.10

# Everything, as for the baseline
uv run --group evals --env-file .env python -m evals --models claude-sonnet-5-5 claude-haiku-5-5 --trials 5 --max-cost-usd 5
```

`--max-cost-usd` is required. The runner refuses a run estimated above it, and stops starting trials once that much is spent. Results go to `evals/results/runs/<timestamp>/` (gitignored). A pull request that changes a tool's name, description or arguments compares its scores with [baseline.md](evals/results/baseline.md): add the `run-evals` label to run them in CI, or run [evals.yml](.github/workflows/evals.yml) by hand. See [evals.md](docs/evals.md).

## Roadmap

1. Local stdio server with the OpenAustralia tools.
2. They Vote For You tools in the same server.
3. Rework tools around tasks, based on how Claude actually uses them.
4. MCP prompts for common workflows, e.g. "brief me on my MP".
5. Maybe later: a remote (Streamable HTTP) server, so the server can be added as a claude.ai custom connector, and a PyPI release.

## Acknowledgements

All the hard work is the [OpenAustralia Foundation](https://www.openaustralia.org.au/)'s. This project only connects their APIs to MCP clients. It is not affiliated with or endorsed by them.
