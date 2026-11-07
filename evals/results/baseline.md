# Eval baseline

The scores of the tools as they are at commit `cdfc08b` (#22). A pull request that changes a tool's name, description or arguments, or the server `instructions`, runs the evals again and compares with this. Run `20261107T103929Z`, anthropic 2.3.0. See [evals.md](../../docs/evals.md).

Notes:

- The member cases are graded on their expected calls, not on a link in the answer, and the list cases don't need a link (see [evals.md](../../docs/evals.md#cases)).
- `mp-3142` on Haiku: the harness no longer sends a 404 for the neighbours Claude asks for most. The failures are Claude checking more neighbours after 3141 and 3145 already gave Josh Burns, or trying postcodes further away, past the 4 calls the case allows.
- `pasted-link` on Haiku: both failing trials read the whole speech but didn't link it.
- Cost per trial: Sonnet 5.5 $0.0282, Haiku 5.5 $0.0015.

23 cases, 5 trials each, on claude-sonnet-5-5 (effort high), claude-haiku-5-5 (effort medium), with the `current` variant of the tools.

## Scores

| Model | Tag | Cases | Mean pass rate | Passed every trial | Calls per trial | Failed calls per trial | Input tokens per trial |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | regression | 22 | 100% | 22/22 | 1.55 | 0.23 | 9,253 |
| claude-sonnet-5-5 | capability | 1 | 100% | 1/1 | 3.00 | 0.00 | 12,477 |
| claude-haiku-5-5 | regression | 22 | 97% | 21/22 | 1.64 | 0.28 | 9,748 |
| claude-haiku-5-5 | capability | 1 | 60% | 0/1 | 3.00 | 0.00 | 14,749 |

Cost: $3.4237 for 230 trials, $0.0149 per trial.

## Cases

| Case | Tags | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---|---|---|
| housing-by-person-id | regression, search | 5/5, 2.0 calls | 5/5, 1.0 calls |
| members-by-name | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-by-person-id | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-former-from-hansard | regression, members, search | 5/5, 3.0 calls | 5/5, 3.0 calls |
| members-greens-senators | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-greens | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| members-senator-housing | regression, members, search | 5/5, 2.0 calls | 5/5, 2.4 calls |
| members-senators-tas | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-0000 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3056 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-3142 | regression, members | 5/5, 3.0 calls | 2/5, 5.6 calls |
| mp-3181 | regression, members | 5/5, 1.0 calls | 5/5, 1.0 calls |
| mp-housing-3056 | regression, search | 5/5, 2.0 calls | 5/5, 2.0 calls |
| mp-housing-read-3056 | regression, read | 5/5, 5.0 calls | 5/5, 5.0 calls |
| mp-recent-3056 | regression, search | 5/5, 2.0 calls | 5/5, 2.0 calls |
| ndis-search | regression, search | 5/5, 1.0 calls | 5/5, 1.0 calls |
| ndis-senate-read | regression, read | 5/5, 2.0 calls | 5/5, 2.0 calls |
| no-results | regression, search | 5/5, 1.0 calls | 5/5, 1.0 calls |
| off-topic | regression | 5/5, 0.0 calls | 5/5, 0.0 calls |
| pasted-link | capability, read | 5/5, 3.0 calls | 3/5, 3.0 calls |
| search-without-a-topic | regression, search | 5/5, 0.0 calls | 5/5, 0.0 calls |
| senate-gid | regression, read | 5/5, 1.0 calls | 5/5, 1.0 calls |
| two-pages | regression, read | 5/5, 2.0 calls | 5/5, 2.0 calls |

## Failures

- `mp-3142` on claude-haiku-5-5, 2 trials: 6 calls, more than 4
- `mp-3142` on claude-haiku-5-5, 1 trial: 8 calls, more than 4
- `pasted-link` on claude-haiku-5-5, 2 trials: answer cites no url from a tool result
