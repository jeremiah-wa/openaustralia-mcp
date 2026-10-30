# Eval baseline

The scores of the tools as they are at commit `834481a` (#6). A pull request that changes a tool's name, description or arguments, or the server `instructions`, runs the evals again and compares with this. Run `20261026T100356Z`, anthropic 2.3.0. See [evals.md](../../docs/evals.md).

Notes:

- `mp-3142`: most failures come from the harness, not the tools. Claude usually tries postcode 3141 first, and 3141 has no recorded response, so it gets a 404. `get_members` reports a 404 as "OpenAustralia request failed", which reads as a temporary error, so Claude retries. Recording 3141 would fix the case.
- `pasted-link` passes on both models, so reading a pasted OpenAustralia link already works.
- Cost per trial: Sonnet 5.5 $0.0281, Haiku 5.5 $0.0015.

16 cases, 5 trials each, on claude-sonnet-5-5 (effort high), claude-haiku-5-5 (effort medium).

## Scores

| Model | Tag | Cases | Mean pass rate | Passed every trial |
|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 15 | 99% | 14/15 |
| claude-sonnet-5-5 | capability | 1 | 100% | 1/1 |
| claude-haiku-5-5 | regression | 15 | 91% | 12/15 |
| claude-haiku-5-5 | capability | 1 | 100% | 1/1 |

Cost: $2.3663 for 160 trials, $0.0148 per trial.

## Cases

| Case | Tags | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---|---|---|
| housing-by-person-id | regression, search | 5/5 | 5/5 |
| mp-0000 | regression, members | 5/5 | 5/5 |
| mp-3056 | regression, members | 5/5 | 5/5 |
| mp-3142 | regression, members | 4/5 | 0/5 |
| mp-3181 | regression, members | 5/5 | 5/5 |
| mp-housing-3056 | regression, search | 5/5 | 5/5 |
| mp-housing-read-3056 | regression, read | 5/5 | 5/5 |
| mp-recent-3056 | regression, search | 5/5 | 4/5 |
| ndis-search | regression, search | 5/5 | 5/5 |
| ndis-senate-read | regression, read | 5/5 | 5/5 |
| no-results | regression, search | 5/5 | 5/5 |
| off-topic | regression | 5/5 | 5/5 |
| pasted-link | capability, read | 5/5 | 5/5 |
| search-without-a-topic | regression, search | 5/5 | 5/5 |
| senate-gid | regression, read | 5/5 | 4/5 |
| two-pages | regression, read | 5/5 | 5/5 |

## Failures

- `mp-3142` on claude-sonnet-5-5, 1 trial: 6 calls, more than 4
- `mp-3142` on claude-haiku-5-5, 3 trials: 6 calls, more than 4
- `mp-3142` on claude-haiku-5-5, 1 trial: 7 calls, more than 4
- `mp-3142` on claude-haiku-5-5, 1 trial: 9 calls, more than 4
- `mp-recent-3056` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result
- `senate-gid` on claude-haiku-5-5, 1 trial: answer cites no url from a tool result
