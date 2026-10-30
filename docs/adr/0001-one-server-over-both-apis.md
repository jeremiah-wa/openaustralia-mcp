# One server over both APIs

OpenAustralia and They Vote For You are separate APIs, so each could have its own MCP server. We run one server with two API clients, because speech and votes join on the member, both APIs use the [same `person_id`](../api-notes.md#they-vote-for-you), and one server can name things clearly.
