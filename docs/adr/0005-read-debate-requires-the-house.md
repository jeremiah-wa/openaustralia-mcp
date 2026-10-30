# `read_debate` requires the house

A `gid` looks like a unique ID, but [`gid`s repeat across houses](../api-notes.md#openaustralia), and asking the wrong house silently returns a different speech. So `house` is a required argument with no default, and `search_hansard` hits carry the house for the next call.
