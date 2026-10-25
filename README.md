# openaustralia-mcp

An MCP server that lets Claude (and other MCP clients) answer questions about the federal Australian Parliament: who represents an electorate, what members have said in Hansard, and how they vote.

It is a thin layer over two existing APIs run by the [OpenAustralia Foundation](https://www.openaustralia.org.au/):

- **[OpenAustralia](https://www.openaustralia.org.au/api/)**: members, electorates, Hansard and debates.
- **[They Vote For You](https://theyvoteforyou.org.au/)**: votes in Parliament (divisions) and policy positions.

> **Status: draft.** This README describes the planned first release. The server hasn't been built yet, so the install commands below won't work until it is.

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
| `read_debate` | OpenAustralia | Read the full text of a debate item by `gid`, a page at a time. |
| `get_policies` / `get_policy` | They Vote For You | Policy topics and how each member's votes line up with them. |
| `get_votes` / `get_vote` | They Vote For You | Individual votes in Parliament (divisions) and how each member voted. |

All tools are read-only.

## Requirements

- [uv](https://docs.astral.sh/uv/) (to install and run the server)
- An OpenAustralia API key: <https://www.openaustralia.org.au/api/key> (free for low-volume, non-commercial use)
- Optional: a They Vote For You API key, for the voting tools. Get one by signing in at <https://theyvoteforyou.org.au/>.

Each key is optional. If a key is missing or rejected, the tools that need it return a message saying so and linking to where to get one. The other tools keep working.

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
        "git+https://github.com/<your-github-user>/openaustralia-mcp",
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
claude mcp add openaustralia -e OPENAUSTRALIA_API_KEY=your-openaustralia-key -e THEYVOTEFORYOU_API_KEY=your-theyvoteforyou-key -- uvx --from git+https://github.com/<your-github-user>/openaustralia-mcp openaustralia-mcp
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
git clone https://github.com/<your-github-user>/openaustralia-mcp
cd openaustralia-mcp
uv sync
uv run pytest
```

- Unit tests run against recorded API responses and don't need a key.
- Set `OPENAUSTRALIA_API_KEY` (and optionally `THEYVOTEFORYOU_API_KEY`) to also run the live smoke tests.
- To poke at the tools by hand, use [MCP Inspector](https://github.com/modelcontextprotocol/inspector) v2 (needs Node 22.19 or later). Keep `@latest` in the command, or npx may run an old cached v1:

```bash
# Web UI
npx @modelcontextprotocol/inspector@latest uv run openaustralia-mcp

# CLI, e.g. to list the tools
npx @modelcontextprotocol/inspector@latest --cli --method tools/list uv run openaustralia-mcp
```

Copy `.env.example` to `.env` to keep keys out of your shell history. `.env` is gitignored.

See [architecture.md](docs/architecture.md) for how the server is put together.

## Roadmap

1. Local stdio server with the OpenAustralia tools.
2. They Vote For You tools in the same server.
3. Rework tools around tasks, based on how Claude actually uses them.
4. MCP prompts for common workflows, e.g. "brief me on my MP".
5. Maybe later: a remote (Streamable HTTP) server, so the server can be added as a claude.ai custom connector, and a PyPI release.

## Acknowledgements

All the hard work is the [OpenAustralia Foundation](https://www.openaustralia.org.au/)'s. This project only connects their APIs to MCP clients. It is not affiliated with or endorsed by them.
