# One `get_members` tool for all member lookups

OpenAustralia has four member functions, and the tools otherwise follow the API one to one. Member lookup doesn't: `get_members` covers all four, with more parameters rather than more tools. [#8](https://github.com/jeremiah-wa/openaustralia-mcp/issues/8) measured it against four tools (`get_members` by postcode, `get_member`, `get_senators`, `search_members`) on Sonnet 5.5 and Haiku 5.5 before either was built. They were equally reliable: both passed every trial on 5 of 7 member cases on Sonnet, and 4 of 7 on Haiku. One tool took fewer calls per trial, 1.43 against 1.57 on Sonnet and 1.54 against 1.69 on Haiku, and 11 to 13% fewer input tokens. With four tools, Claude often fetched a party's Senators twice, from `search_members` and again from `get_senators`, while it filled the extra parameters of the one tool without a wrong or unknown argument.

The full results are in [member-lookup.md](../../evals/results/member-lookup.md).
