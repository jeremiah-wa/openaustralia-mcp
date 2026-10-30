# A hand-written eval runner with deterministic graders

We measure Claude's tool use with our own runner on the Anthropic SDK's tool runner, not an eval framework. It uses the same seam as the tests, over the in-memory MCP client with recorded responses, so it needs no subprocess and no OpenAustralia key. Its Python graders can check argument values and chaining, and it sees Claude's raw tool input, the only place a misnamed argument shows up, because the server drops unknown arguments. It was also the cheapest per run. What it gives up is being a real client: the runner chooses the system prompt, and there's no tool search.

The graders are deterministic, with no LLM judge yet, because tool choice, arguments and facts from the fixtures can be checked exactly.

## Considered options

- **`claude plugin eval`:** it only covers Claude Code, its graders are regexes with no custom code, and each trial costs an estimated several times as much. It's worth adding later on a small subset of cases, because it runs the real Claude Code.
- **Inspect AI:** a large framework whose concepts are about evals, not MCP, and it reaches MCP servers only as a separate process or over HTTP.
- **promptfoo:** it brings Node into a Python repo, and it wasn't confirmed that its Anthropic MCP loop produces the traces its `trajectory:*` assertions read.

The full comparison is in [this comment on #5](https://github.com/jeremiah-wa/openaustralia-mcp/issues/5#issuecomment-6411528943).
