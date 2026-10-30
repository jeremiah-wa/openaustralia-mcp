# API notes

What OpenAustralia and They Vote For You actually do, as far as live calls have shown. Both API docs sites are behind a Cloudflare challenge, so exact parameters come from the `openaustralia` Python package docs and from live calls. Recorded responses are in `tests/fixtures/`. Where something hasn't been verified yet, it's marked **unverified**.

## OpenAustralia

- **Request:** `GET https://www.openaustralia.org.au/api/<function>?key=…&output=js&…`. `getRepresentatives` takes `postcode`, `date`, `party` and `search`.
- **Response:** a JSON array. IDs come back as strings (`"person_id": "10887"`). Name, party and electorate are `full_name`, `party` and `constituency`. `office` lists positions, where `to_date: "9999-12-31"` means current.
- **Errors:** HTTP 200 with `{"error": "…"}`. A bad key gives `"Invalid API key."` and an unknown postcode gives `"Unknown postcode"`.
- **Postcodes in abolished electorates:** OpenAustralia's postcode data still includes electorates abolished in the 2025 redistribution, such as Higgins. `getRepresentatives` puts `false` in the list where a division has no current member. 3142 gives `[false]`, and 3181 gives `[false, Josh Burns]`. `get_members` skips the `false` entries. If some were skipped, it adds a `note` saying the list may be incomplete. If none are left, it says no current member is on record.
- **Encoding:** the header says `charset=iso-8859-1`, but all 150 current members come back as plain ASCII.
- **Member page URL:** `https://www.openaustralia.org.au/mp/?p=<person_id>` is **unverified**. The website returns 403 to scripts.
- **Past dates:** `getRepresentatives?date=2015-01-01` returned `{}`, not a list. Not yet understood.
- **`getHansard`** takes `search`, `person`, `order` and `page`, and needs at least one. With none, it returns `{"error": "No parameter provided…"}`. Passing `num` gives HTTP 500, so a page is always 20 rows. The default `order` is `d` (newest first). `r` sorts by relevance.
- **`getHansard` response:** `{"info": {…, "total_results"}, "rows": […]}`. No hits gives `rows: {}` (an empty PHP array, not `[]`), also for a `person` that doesn't exist. Each row has `gid`, `hdate`, `major` (`"1"` House, `"101"` Senate), `body`, `listurl`, `speaker` (with `person_id`) and `parent.body` (the debate title). All 300 rows sampled had a speaker and a parent.
- **Hansard excerpts:** `body` is already an excerpt of about 400 characters, made by OpenAustralia. It contains `<span class="hi">` around the search terms and HTML entities such as `&#8212;`. `listurl` is a relative, HTML-escaped link to the speech, under `/debates/` or `/senate/`.
- **`getDebates`** takes `type` (`representatives` or `senate`) and `gid`. Without a `type` it returns `{"error": "You must supply a type"}`, and an unknown `type` gives `{"error": "Unknown type"}`.
- **`gid`s repeat across houses.** `2026-06-23.80.1` is Peter Khalil in the House and Lidia Thorpe in the Senate. The wrong `type` silently returns the other house's speech, so the house has to come with the `gid`. `search_hansard` hits carry it.
- **`getDebates` response:** a JSON array of entries, each with `gid`, `htype`, `hdate`, `body` and `listurl`. A speech `gid` gives three entries: the section heading (`htype` 10, e.g. "Matters of Public Importance"), the subsection heading (`htype` 11, e.g. "Budget") and the speech (`htype` 12, with `speaker`). The two headings together make `getHansard`'s `parent.body`. A heading `gid` (the `id=` in a speech's `listurl`) gives the whole debate: for `2026-06-23.78.2`, the 2 headings and 14 speeches. Headings have `speaker: {}` or no `speaker`.
- **Debate text:** `body` is HTML with `<p>` and `<i>` tags and entities such as `&#8212;`. One speech by Peter Khalil is 8,715 characters as plain text, and its whole debate is about 51,000.
- **Unknown `gid`:** HTTP 404 with an HTML page, not an `{"error": …}` body. A malformed `gid` gives the same.

## They Vote For You

- **Request:** `GET https://theyvoteforyou.org.au/api/v1/<path>.json?key=…`, e.g. `people.json`, `people/<id>.json`, `divisions.json`, `divisions/<id>.json`. `divisions.json` takes `house`, `start_date` and `end_date`, and returns up to 100 votes.
- **Response:** real JSON (`application/json; charset=utf-8`), with integer IDs. `people.json` lists current members only: 226, the same as OpenAustralia's 150 Representatives plus 76 Senators.
- **Same IDs as OpenAustralia:** a person's `id` is OpenAustralia's `person_id`, and `latest_member.id` is OpenAustralia's `member_id`. All 226 current members matched on both, and on name, electorate and house. Former members match too: the 8 former members checked from a 2015 vote came back with the same name from OpenAustralia's `getRepresentative?id=<id>`. In a vote, each member is `member.person.id`.
- **Party labels differ for presiding officers:** OpenAustralia says `Speaker`, `President` and `Deputy-President`, and They Vote For You says `SPK`, `PRES` and `DPRES`.
- **Policy scores:** `people/<id>.json` includes `policy_comparisons`, each with the policy, `agreement` (a percentage as a string, e.g. `"100"`) and `voted`.
