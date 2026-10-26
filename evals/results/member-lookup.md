# Member lookup: more parameters or more tools

The results of [#8](https://github.com/jeremiah-wa/openaustralia-mcp/issues/8): one `get_members` with more parameters (`parameters`), or more member tools (`tools`). [evals.md](../../docs/evals.md#member-lookup-8) describes both variants, the measures and the decision rule, which was committed before the full runs. Runs `20261026T122610Z` (parameters) and `20261026T123043Z` (tools), at commit `bd06ddb`, anthropic 2.3.0, mcp 2.3.0. 14 cases × 5 trials, on Sonnet 5.5 (effort high) and Haiku 5.5 (effort medium).

## Decision: `parameters`

| Member cases (7) | parameters, Sonnet | tools, Sonnet | parameters, Haiku | tools, Haiku |
|---|---|---|---|---|
| Passed every trial | 5/7 | 5/7 | 4/7 | 4/7 |
| Mean pass rate | 94% | 83% | 80% | 83% |
| Calls per trial | **1.43** | 1.57 | **1.54** | 1.69 |
| Failed calls per trial | 0.14 | 0.14 | **0.26** | 0.37 |
| Input tokens per trial | **8,101** | 8,967 | **8,703** | 9,824 |

1. **Reliability: a tie.** Each variant passed every trial on 5 of the 7 member cases on Sonnet, and 4 of 7 on Haiku. Neither broke a `get_members` regression case: both scored 7/7 on Sonnet, and on Haiku `parameters` scored 7/7 and `tools` 6/7, which was one uncited URL in `mp-housing-3056`.
2. **Calls: `parameters` made fewer on both models**, so it wins by rule 2.

## Why

- **Most of the gap in calls comes from one case, `members-greens`.** With `tools`, Claude called `search_members(party=Greens)` and then `get_senators(party=Greens)`, fetching the same Senators twice. Sonnet did this in 5 of 5 trials, and Haiku in 1. With one tool, every trial made one call. This is the selection ambiguity the issue quotes: two tools that both answer the question, and Claude used both.
- **Claude filled the extra parameters correctly.** Over 70 member-case trials, `parameters` had no wrong or unknown arguments and no refused combinations. It set `house` where it helped (`get_members(party=Greens, house=senate)`, `get_members(state=TAS, house=senate)`), and used `person_id` on its own. The risk on that side, plausible but wrong values, didn't show up.
- **Every failure in both runs is an answer that didn't cite the expected URL,** never a wrong tool or a wrong argument. Answers that left out the URL, such as `members-former-from-hansard` on Haiku (0/5 with `parameters`, 2/5 with `tools`) and `members-senators-tas` on Sonnet (5/5 and 2/5), go both ways and decide nothing. A judge for answer quality, or tighter citation guidance in the instructions, would be a separate change.
- **Input tokens:** `tools` sends 11% more per trial on Sonnet and 13% more on Haiku, for the extra tool definitions on every turn.
- **Former members:** both variants found Keith Wolahan the same way. A name search failed, they took his `person_id` from the Ruby Princess hit, then looked him up by it. That's 3 calls on every trial of both.

## Harness gaps

The smoke runs found one gap, searches for former Greens MPs, which was recorded before the full runs. The full runs found more, all on Haiku in `members-senator-housing`. Each request got a 404, which reads as "OpenAustralia request failed", where the real API would have answered:

- `tools`: `get_senators(state=ACT)`, twice, before finding David Pocock by name.
- `parameters`: `search_hansard(query=housing)` without a `person_id`, twice, before searching with his.
- Both: `read_debate` on his speech of 2 July 2026, two calls in one trial each.

Each variant lost two calls to its own gap, and two to `read_debate`. Taking each variant's own gap out, Haiku's calls per trial would be about 1.49 with `parameters` and 1.63 with `tools`, so the decision stands. Sonnet hit none. The responses were recorded after these runs, for future ones.

## Cost

$2.1374 (parameters) and $2.4236 (tools) for the full runs, $4.56 in all. The smoke runs before them cost $0.92.

## Eval run 20261026T122610Z

14 cases, 5 trials each, on claude-sonnet-5-5 (effort high), claude-haiku-5-5 (effort medium), with the `parameters` variant of the tools.

### Scores

| Model | Tag | Cases | Mean pass rate | Passed every trial | Calls per trial | Failed calls per trial | Input tokens per trial |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 7 | 100% | 7/7 | 1.86 | 0.14 | 11,640 |
| claude-sonnet-5-5 | capability | 7 | 94% | 5/7 | 1.43 | 0.14 | 8,101 |
| claude-haiku-5-5 | regression | 7 | 100% | 7/7 | 1.86 | 0.14 | 13,054 |
| claude-haiku-5-5 | capability | 7 | 80% | 4/7 | 1.54 | 0.26 | 8,703 |

Cost: $2.1374 for 140 trials, $0.0153 per trial.

### Cases

| Case | Tags | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---|---|---|
| members-by-name | capability, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-by-person-id | capability, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-former-from-hansard | capability, members, search | 4/5, 3.0 calls | 0/5, 3.0 calls |
| members-greens-senators | capability, members | 4/5, 1.0 calls | 5/5, 1.0 calls |
| members-greens | capability, members | 5/5, 1.0 calls | 4/5, 1.0 calls |
| members-senator-housing | capability, members, search | 5/5, 2.0 calls | 5/5, 2.8 calls |
| members-senators-tas | capability, members | 5/5, 1.0 calls | 4/5, 1.0 calls |
| mp-0000 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3056 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3181 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-housing-3056 | regression, search | 5/5, 2.0 calls | 5/5, 2.0 calls |
| mp-housing-read-3056 | regression, read | 5/5, 5.0 calls | 5/5, 5.0 calls |
| mp-recent-3056 | regression, search | 5/5, 2.0 calls | 5/5, 2.0 calls |
| ndis-search | regression, search | 5/5, 1.0 calls | 5/5, 1.0 calls |

### Failures

- `members-former-from-hansard` on claude-sonnet-5-5, 1 trial: answer is missing: https://www.openaustralia.org.au/mp/?p=10990
- `members-former-from-hansard` on claude-haiku-5-5, 5 trials: answer is missing: https://www.openaustralia.org.au/mp/?p=10990
- `members-greens-senators` on claude-sonnet-5-5, 1 trial: answer cites no url from a tool result
- `members-greens` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result
- `members-senators-tas` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result

### Compared with the baseline

This run used the `parameters` variant of the tools, and the baseline the `current` one.

| Model | Tag | Cases | Baseline | This run | Change |
|---|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 7 | 100% | 100% | 0 points |
| claude-haiku-5-5 | regression | 7 | 97% | 100% | +3 points |

| Case | Model | Baseline | This run |
|---|---|---|---|
| mp-recent-3056 | claude-haiku-5-5 | 4/5 | 5/5 |

Not in the baseline: `members-by-name`, `members-by-person-id`, `members-former-from-hansard`, `members-greens-senators`, `members-greens`, `members-senator-housing`, `members-senators-tas`.

With about 100 trials per model, differences under about 10 points are noise (docs/evals.md).
## Eval run 20261026T123043Z

14 cases, 5 trials each, on claude-sonnet-5-5 (effort high), claude-haiku-5-5 (effort medium), with the `tools` variant of the tools.

### Scores

| Model | Tag | Cases | Mean pass rate | Passed every trial | Calls per trial | Failed calls per trial | Input tokens per trial |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 7 | 100% | 7/7 | 1.86 | 0.14 | 13,781 |
| claude-sonnet-5-5 | capability | 7 | 83% | 5/7 | 1.57 | 0.14 | 8,967 |
| claude-haiku-5-5 | regression | 7 | 97% | 6/7 | 1.86 | 0.14 | 14,252 |
| claude-haiku-5-5 | capability | 7 | 83% | 4/7 | 1.69 | 0.37 | 9,824 |

Cost: $2.4236 for 140 trials, $0.0173 per trial.

### Cases

| Case | Tags | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---|---|---|
| members-by-name | capability, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-by-person-id | capability, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-former-from-hansard | capability, members, search | 5/5, 3.0 calls | 2/5, 3.0 calls |
| members-greens-senators | capability, members | 2/5, 1.0 calls | 4/5, 1.0 calls |
| members-greens | capability, members | 5/5, 2.0 calls | 5/5, 2.0 calls |
| members-senator-housing | capability, members, search | 5/5, 2.0 calls | 5/5, 2.8 calls |
| members-senators-tas | capability, members | 2/5, 1.0 calls | 3/5, 1.0 calls |
| mp-0000 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3056 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3181 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-housing-3056 | regression, search | 5/5, 2.0 calls | 4/5, 2.0 calls |
| mp-housing-read-3056 | regression, read | 5/5, 5.0 calls | 5/5, 5.0 calls |
| mp-recent-3056 | regression, search | 5/5, 2.0 calls | 5/5, 2.0 calls |
| ndis-search | regression, search | 5/5, 1.0 calls | 5/5, 1.0 calls |

### Failures

- `members-former-from-hansard` on claude-haiku-5-5, 3 trials: answer is missing: https://www.openaustralia.org.au/mp/?p=10990
- `members-greens-senators` on claude-sonnet-5-5, 3 trials: answer cites no url from a tool result
- `members-greens-senators` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result
- `members-senators-tas` on claude-sonnet-5-5, 3 trials: answer cites no url from a tool result
- `members-senators-tas` on claude-haiku-5-5, 2 trials: answer cites no url from a tool result
- `mp-housing-3056` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result

### Compared with the baseline

This run used the `tools` variant of the tools, and the baseline the `current` one.

| Model | Tag | Cases | Baseline | This run | Change |
|---|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 7 | 100% | 100% | 0 points |
| claude-haiku-5-5 | regression | 7 | 97% | 97% | 0 points |

| Case | Model | Baseline | This run |
|---|---|---|---|
| mp-housing-3056 | claude-haiku-5-5 | 5/5 | 4/5 |
| mp-recent-3056 | claude-haiku-5-5 | 4/5 | 5/5 |

Not in the baseline: `members-by-name`, `members-by-person-id`, `members-former-from-hansard`, `members-greens-senators`, `members-greens`, `members-senator-housing`, `members-senators-tas`.

With about 100 trials per model, differences under about 10 points are noise (docs/evals.md).
