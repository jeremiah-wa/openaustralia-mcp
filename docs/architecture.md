# Architecture

How the OpenAustralia MCP server is put together, and why. It started as a draft before any code existed, and it's updated as tools are built. Where something hasn't been verified yet, it's marked **unverified**.

## Overview

The server is a local MCP server, written in Python, that Claude Desktop or Claude Code starts as a child process and talks to over stdio. When Claude calls a tool, the server makes the matching HTTP GET calls to OpenAustralia or They Vote For You, cuts the response down to what the model needs, adds a source link, and returns it.

```mermaid
flowchart LR
    user([User]) --> client["MCP client<br/>(Claude Desktop / Claude Code)"]
    client <-- "stdio (JSON-RPC)" --> server["openaustralia-mcp<br/>(local Python process)"]
    server -- "HTTPS GET + key" --> oa["OpenAustralia API<br/>openaustralia.org.au/api"]
    server -- "HTTPS GET + key" --> tvfy["They Vote For You API<br/>theyvoteforyou.org.au/api/v1"]
    env[["Env vars<br/>OPENAUSTRALIA_API_KEY<br/>THEYVOTEFORYOU_API_KEY"]] -.-> server
```

The server stores nothing on disk and never changes data. Keys are read from the environment the client passes to the process.

## Components

```mermaid
flowchart TB
    subgraph entry["Entry points"]
        stdio["stdio entry<br/>(stage 1)"]
        http["HTTP entry<br/>(later stage)"]
    end

    subgraph core["Server core (transport-agnostic)"]
        factory["Server factory<br/>build_server(http_client, config)"]
        tools["Tool layer<br/>names, descriptions, instructions"]
        shape["Result shaping<br/>trim · paginate · attribute"]
        cache["Cache<br/>TTL + bounded LRU"]
    end

    subgraph clients["API clients"]
        oac["OpenAustralia client"]
        tvc["They Vote For You client"]
    end

    stdio --> factory
    http -.-> factory
    factory --> tools
    tools --> shape
    tools --> oac
    tools -.-> tvc
    tools -.-> cache
    cache -.-> oac
    cache -.-> tvc
```

Dashed lines aren't built yet.

| Component | Responsibility |
|---|---|
| **Entry points** | Read config, build the server, attach a transport. Stage 1 ships stdio only. The HTTP entry point is a later addition and doesn't change the core. |
| **Server factory** | The single construction point. It takes an HTTP client and the config, so tests can swap in fakes (see [Testing](#testing)). A clock parameter is added along with the cache. |
| **Tool layer** | Registers the tools with the `mcp` SDK (`MCPServer`, called FastMCP before 2.x) and holds the descriptions and the server `instructions` that tell the model how to chain tools. |
| **Result shaping** | Turns raw API responses into small, citable results (the result models in `models.py`). This is where most of the design work goes. |
| **Cache** | Will avoid repeat calls for data that rarely or never changes. Not built yet. |
| **API clients** | One per API, though only the OpenAustralia client is built so far. They build requests, attach the key, turn error responses into typed errors, and parse responses into pydantic models that keep the API's own field names (e.g. `Representative`). They don't know anything about MCP. The tool functions decide what to do with gaps in the data, and map API models onto result models. |

## Tools

At first the tools follow the API functions one to one, with three changes: results are trimmed, results include the IDs the next call needs, and some names are changed so they don't mislead the model. Once real use shows where Claude struggles, the tools will be reworked around tasks.

| Tool | API call(s) | Returns |
|---|---|---|
| `get_members` | OA `getRepresentatives`, `getRepresentative`, `getSenators`, `getSenator` | Members with `person_id`, house, party, electorate/state |
| `get_electorates` | OA `getDivisions` | Electorates (electoral divisions) |
| `search_hansard` | OA `getHansard` | 20 hits (one OpenAustralia page): speaker, `person_id`, date, house, debate title, excerpt, `gid`, URL. Plus the total number of hits |
| `read_debate` | OA `getDebates` (by `gid` and `type`) | Up to ~4,000 characters per call, plus `offset` for the next page |
| `get_policies`, `get_policy` | TVFY `/policies` | Policy topics, with each member's agreement score |
| `get_votes`, `get_vote` | TVFY `/divisions` | Individual votes and how each member voted |

Notes on naming:

- **"Divisions" means two different things.** OpenAustralia's `getDivisions` returns electorates, while They Vote For You's `/divisions` returns votes. The tools are named `get_electorates` and `get_votes` so the model can't mix them up.
- **Only one tool looks up members.** They Vote For You's people data is folded into the policy and vote results instead of getting its own tool.
- **`getComments` is left out.**

What each API actually does, from live calls, is in [api-notes.md](api-notes.md).

Status: `get_members` covers postcode lookup of Representatives only. Name and party search and Senators come next. `search_hansard` searches by query, `person_id` or both, and returns the first page of 20. Paging and `order` come next. `read_debate` reads a speech gid, or a heading gid for the whole debate, 4,000 characters at a time. Its cache by `gid` comes next.

## A typical question

"What has my MP said about housing, and how do they vote on it?"

```mermaid
sequenceDiagram
    participant C as Claude
    participant S as openaustralia-mcp
    participant OA as OpenAustralia
    participant TV as They Vote For You

    C->>S: get_members(postcode="3056")
    S->>OA: getRepresentatives?postcode=3056
    OA-->>S: member list
    S-->>C: person_id=10001, name, party

    C->>S: search_hansard(query="housing", person_id=10001)
    S->>OA: getHansard?search=housing&person=10001
    OA-->>S: raw hits
    S-->>C: 20 excerpts with gid + source URL

    C->>S: read_debate(gid="2026-09-10.42.1", house="representatives")
    S->>OA: getDebates?gid=...
    OA-->>S: full debate text
    S-->>C: first 4,000 chars + next offset

    C->>S: get_policies(person_id=10001, query="housing")
    S->>TV: /policies, /people/10001
    TV-->>S: policy scores
    S-->>C: "agrees 85% with increasing housing affordability" + source URL
```

Every result includes the IDs the next call needs (`person_id` → `gid`). The model never has to guess at API syntax.

The last step isn't built yet. It relies on They Vote For You using the same `person_id`s as OpenAustralia. Live calls confirmed it does (see [api-notes.md](api-notes.md#they-vote-for-you)), so a `person_id` from `get_members` can be passed straight to the voting tools, with no matching across the two APIs.

## Keys and errors

```mermaid
flowchart TD
    call["Tool called"] --> has{"Key for this API<br/>set?"}
    has -- no --> missing["Return readable message:<br/>'No OpenAustralia key set. Get one at …'"]
    has -- yes --> req["Make API request"]
    req --> ok{"Response has<br/>{error: …}?"}
    ok -- no --> result["Shape and return result"]
    ok -- "yes: bad key" --> rejected["Return readable message:<br/>'Key was rejected. Check it or get a new one at …'"]
    ok -- "yes: other" --> other["Return the API's error text,<br/>with the tool and arguments"]
```

- **Validation is lazy.** The server always starts, and a key problem comes back as a tool result that Claude can explain to the user. Failing at startup would only show up in Claude Desktop as an unhelpful "server disconnected".
- **Each key is independent.** Once the voting tools are built, missing a They Vote For You key will disable only those. The server doesn't read that key yet.
- **Keys never appear in logs, results or errors.** OpenAustralia only accepts the key in the query string, so every request URL contains it. That's why:
  - `build_server` raises the `httpx2` and `httpcore2` loggers to WARNING. At INFO, httpx2 logs every request URL, and the SDK writes INFO logs to stderr.
  - The API clients catch HTTP errors and re-raise them `from None` with the status only, because httpx2 errors carry the request and its URL.
  - Tests check results and captured logs for a sentinel key.
  - A pre-commit hook and CI scan with gitleaks for a key in a `key=` query, a `"key"` field or an `…_API_KEY` setting, in case a fixture or doc is committed unscrubbed.
  - The evals' Anthropic key needs no custom rule. gitleaks' default `anthropic-api-key` rule, which `.gitleaks.toml` keeps, caught a fake key in four forms under v8.28.0: on its own, as `ANTHROPIC_API_KEY=…`, as a JSON value and as a Python argument. It doesn't flag the `.env.example` placeholder.
- **Network failures, non-200 statuses and non-JSON bodies** (such as a Cloudflare challenge page) all return "couldn't be reached" or "didn't respond normally (HTTP …)".

## Result shaping

Hansard responses are long, and model context is limited. The rules:

| Rule | Default |
|---|---|
| Search hits per page | 20, OpenAustralia's fixed page size |
| Excerpt | OpenAustralia's own (~400 characters), with markup stripped and entities decoded |
| `read_debate` page size | ~4,000 characters, with an `offset` for the next page |
| Attribution | Every result ends with a source URL and the licence line |
| Hansard text | Cut, never rewritten or summarised on the server (CC BY-NC-ND: no derivatives) |

These defaults are starting values, to be tuned once recorded responses show real sizes.

## Caching

No cache is built yet, so every call goes to the API. This is the plan. The cache will be in memory only, and lost when the process exits.

| Data | Policy | Why |
|---|---|---|
| Members, electorates | 24-hour TTL | Rarely change, and almost every question looks up a `person_id` |
| TVFY policies | 24-hour TTL | Rarely change |
| Debate text (by `gid` and house) | Bounded LRU (~50 items) | Published Hansard never changes, and paging with `offset` would otherwise download the whole debate again for every page. The key needs the house, because gids repeat across houses |
| Searches | Not cached | New sitting days change the results, and a stale search could silently miss today's debate |

## Testing

The tests use a single seam, the MCP tool call, with a fake HTTP client passed to the factory.

```mermaid
flowchart LR
    test["pytest"] -- "call_tool(name, args)" --> mc["In-memory MCP client"]
    mc --> srv["Server built by<br/>build_server(...)"]
    srv --> fakehttp["Fake HTTP client<br/>(recorded responses)"]
```

- **Unit tests** call tools through an in-memory MCP client, the same way a real client does, and check the result: trimming, IDs, attribution and error messages. HTTP is served from recorded responses, so no key is needed and the tests run in CI. Each recorded response answers only the request it was recorded for (`RECORDED` in `tests/fake_api.py`), and any other request gets a 404.
- **Cache tests** will come with the cache. They'll move a fake clock forward to check the TTL, and count HTTP calls to check that paging through one `gid` fetches it only once.
- **Live smoke tests** use the same tool-level seam with a real HTTP client. They run only when the key env vars are set. CI runs them in `live.yml` every Sunday at 20:17 UTC, by hand, and on pull requests that change them, and fails if the key secret is missing rather than letting them skip.
- **Manual testing** uses MCP Inspector.
- **Evals** check what the tests can't: whether Claude picks the right tool, fills in the right arguments and chains the calls. They run Claude against a server built the same way, with recorded responses routed by request. They cost money and aren't deterministic, so they live outside pytest. CI runs them only in `evals.yml`, by hand or when a pull request gets the `run-evals` label, and the job summary compares the run with the committed baseline. See [evals.md](evals.md).

Nothing below the tool call is tested on its own. That keeps the internals free to change when the tools are reworked around tasks.

## Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Language | Python, `uv`, the official `mcp` SDK (2.x) | Less boilerplate. The focus is MCP, not the language. |
| HTTP client | `httpx2` | The `mcp` 2.x SDK already depends on it, so the server has one HTTP stack, not two |
| Transport | stdio first, with a transport-agnostic core | Local use needs no hosting, and HTTP can be added later without a refactor |
| Servers | One server, two API clients | Speech and votes join on the member, both APIs use the same `person_id`, and one server can name things clearly |
| Tool shape | One tool per API function, for now | Real usage should drive the redesign around tasks |
| Workflow guidance | Server `instructions` and tool descriptions | The model always sees these. Prompts and resources are chosen by the user, not the model. |
| Key validation | On first call | Readable errors instead of an opaque startup crash |
| Hansard search page size | 20 hits, one OpenAustralia page | `getHansard` can't return fewer (`num` gives HTTP 500), and paging can later map straight onto its `page` |
| Hansard excerpt | OpenAustralia's own, markup stripped | It's already short. Cutting further would lose context for little saving. |
| `read_debate` house | A required argument, with no default | gids repeat across houses, and the wrong house silently returns a different speech. `search_hansard` hits already carry the house. |
| `read_debate` text | Each speech after its speaker's name, paragraphs kept, paged by character offset over the joined text | One shape for a single speech and a whole debate. Character offsets stay valid between calls because published Hansard doesn't change. |
| HTTP 404 from OpenAustralia | "Not found", naming the gid and house | `getDebates` sends a 404 page for an unknown gid, and "try again later" would send Claude round in circles |
| Distribution | `uvx --from git+…` | No release process needed. PyPI later. |
| Live tests in CI | A separate weekly workflow, with the OpenAustralia key in a repository secret | Recorded responses can't show the API changing. Weekly keeps the load on a charity's free API small, and a separate workflow keeps the key out of the jobs that run on every push |
| Committed-key check | gitleaks with a custom rule in `.gitleaks.toml`, run by a pre-commit hook and again in CI | GitHub's secret scanning only knows its partners' key formats, which don't include OpenAustralia or They Vote For You. The hook stops a key before it's committed. CI catches clones without the hook, and `--no-verify` |
| Tool-use evals | A hand-written runner on the Anthropic SDK's tool runner, over the in-memory MCP client, with recorded responses routed by request. See [evals.md](evals.md) | Same seam as the tests, no OpenAustralia key, and graders can check argument values and the raw input. Cheapest per run. `claude plugin eval`, Inspect AI and promptfoo were compared in [#5](https://github.com/jeremiah-wa/openaustralia-mcp/issues/5#issuecomment-6411528943) |
| Eval graders | Deterministic: expected calls with arguments matched on value, dependencies rather than an exact order, forbidden calls, unknown arguments, number of calls, facts the answer must contain, and a cited `url`. No LLM judge yet | Tool choice, arguments and facts from the fixtures can be checked exactly. A fixed order rejects other valid paths |
| Eval models and trials | `claude-sonnet-5-5` by default and `claude-haiku-5-5` as the stress test, with effort set explicitly. 5 trials per case, reporting the pass rate and pass^k | Answers vary between runs and sampling can't be turned down. Smaller models are more sensitive to tool design |
| Eval results | JSON per run, gitignored. The baseline is committed as markdown, `evals/results/baseline.md`, and as scores, `evals/results/baseline.json` | Pull requests compare against the baseline without committing every run. CI reads the scores and the cost per trial from the JSON, not from the markdown |
| Evals in CI | A separate workflow, `evals.yml`, run by hand or by the `run-evals` label on a pull request, reporting only | Each full run costs about $2.40, so never on a push. A separate workflow keeps the Anthropic key out of the jobs that run on every push. No threshold until there are a few runs to compare |
| Code licence | MIT | Data licences are documented separately |

## Open questions

- What exact parameters does each OpenAustralia and They Vote For You function take? (`getRepresentatives` is done. See [api-notes.md](api-notes.md#openaustralia).)
- Is `/mp/?p=<person_id>` the right member page URL?
- How well do the result-size defaults hold up against real responses?
- How should tools reject unknown arguments? The `mcp` SDK builds each tool's arguments model with pydantic's default `extra="ignore"` and has no setting to change it. So a misnamed argument is dropped silently: `search_hansard(query="housing", person="10887")` searches every member's speeches. A wrong type, such as a number for `person_id`, is already rejected before any request. A fix would mean setting `extra="forbid"` through the SDK's private `_tool_manager`, or a change upstream.

## Later stages

```mermaid
flowchart LR
    s1["1. Local stdio<br/>OpenAustralia tools"] --> s1b["1b. They Vote For You tools"]
    s1b --> s3["Rework tools around tasks"]
    s3 --> s4["MCP prompts"]
    s4 -.-> s5["Remote HTTP server"]
    s5 -.-> s6["claude.ai connector<br/>(key in x-api-key header)"]
    s6 -.-> s7["OAuth (optional)"]
```

For the remote stages, the server would read keys from request headers instead of env vars, for each request. The core stays the same. Only the entry point and how the config is supplied change.
