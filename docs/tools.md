# Tools

What each tool does, how the tools are named, and how their results are shaped and cached. What the APIs behind them actually do is in [api-notes.md](api-notes.md).

At first the tools follow the API functions one to one, with three changes: results are trimmed, results include the IDs the next call needs, and some names are changed so they don't mislead the model. Once real use shows where Claude struggles, the tools will be reworked around tasks.

| Tool | Status | API call(s) | Returns |
|---|---|---|---|
| `get_members` | Representatives by postcode only. Name and party search and Senators come next | OA `getRepresentatives`, `getRepresentative`, `getSenators`, `getSenator` | Members with `person_id`, house, party, electorate/state |
| `get_electorates` | Not built | OA `getDivisions` | Electorates (electoral divisions) |
| `search_hansard` | Built, by query, `person_id` or both. First page only: paging and `order` come next | OA `getHansard` | 20 hits (one OpenAustralia page): speaker, `person_id`, date, house, debate title, excerpt, `gid`, URL. Plus the total number of hits |
| `read_debate` | Built. Its cache by `gid` comes next | OA `getDebates` (by `gid` and `type`, so `house` is required: [ADR 0005](adr/0005-read-debate-requires-the-house.md)) | A speech, or the whole debate for a heading `gid`. Up to ~4,000 characters per call, plus `offset` for the next page |
| `get_policies`, `get_policy` | Not built | TVFY `/policies` | Policy topics, with each member's agreement score |
| `get_votes`, `get_vote` | Not built | TVFY `/divisions` | Individual votes and how each member voted |

## Naming

- **"Divisions" means two different things.** OpenAustralia's `getDivisions` returns electorates, while They Vote For You's `/divisions` returns votes. The tools are named `get_electorates` and `get_votes` so the model can't mix them up.
- **Only one tool looks up members.** They Vote For You's people data is folded into the policy and vote results instead of getting its own tool.
- **`getComments` is left out.**

## Result shaping

Hansard responses are long, and model context is limited. The rules:

| Rule | Default |
|---|---|
| Search hits per page | 20, OpenAustralia's fixed page size |
| Excerpt | OpenAustralia's own (~400 characters), with markup stripped and entities decoded |
| `read_debate` page size | ~4,000 characters, with an `offset` for the next page |
| Attribution | Every result ends with a source URL and the licence line |
| Hansard text | Cut, never rewritten or summarised on the server ([ADR 0003](adr/0003-cut-hansard-never-rewrite-it.md)) |

These defaults are starting values, to be tuned once recorded responses show real sizes.

## Caching

No cache is built yet, so every call goes to the API. This is the plan. The cache will be in memory only, and lost when the process exits.

| Data | Policy | Why |
|---|---|---|
| Members, electorates | 24-hour TTL | Rarely change, and almost every question looks up a `person_id` |
| TVFY policies | 24-hour TTL | Rarely change |
| Debate text (by `gid` and house) | Bounded LRU (~50 items) | Published Hansard never changes, and paging with `offset` would otherwise download the whole debate again for every page. The key needs the house, because gids repeat across houses |
| Searches | Not cached | New sitting days change the results, and a stale search could silently miss today's debate |
