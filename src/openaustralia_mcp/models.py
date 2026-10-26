"""Tool result models: the small, citable shapes the tools return."""

import html
import re
from typing import Literal

from pydantic import BaseModel, Field

from openaustralia_mcp.openaustralia import HANSARD_LICENCE, SITE_URL, DebateEntry, HansardRow, Representative

# Characters of debate text per read_debate call.
DEBATE_PAGE_SIZE = 4000


class Member(BaseModel):
    person_id: str = Field(description="Stable ID for this person. Pass it to other tools.")
    name: str
    party: str
    electorate: str
    house: Literal["representatives"]
    positions: list[str] = Field(description="Current ministerial or other offices, if any.")
    url: str = Field(description="The member's page on OpenAustralia. Cite it.")

    @classmethod
    def from_representative(cls, representative: Representative) -> "Member":
        return cls(
            person_id=representative.person_id,
            name=representative.full_name,
            party=representative.party or "",
            electorate=representative.constituency or "",
            house="representatives",
            positions=representative.current_positions,
            url=representative.url,
        )


class MembersResult(BaseModel):
    members: list[Member]
    note: str | None = Field(default=None, description="A caveat to pass on to the user, if any.")
    source_url: str
    licence: str


class HansardHit(BaseModel):
    gid: str = Field(description="Identifies this speech in Hansard.")
    date: str
    house: Literal["representatives", "senate"]
    speaker: str
    person_id: str = Field(description="The speaker's person_id. Pass it to other tools.")
    debate: str = Field(description="Title of the debate the speech was part of.")
    excerpt: str = Field(description="The part of the speech that matched, as OpenAustralia excerpts it.")
    url: str = Field(description="The speech on OpenAustralia. Cite it.")

    @classmethod
    def from_row(cls, row: HansardRow) -> "HansardHit":
        return cls(
            gid=row.gid,
            date=row.hdate,
            house="senate" if row.major == "101" else "representatives",
            speaker=f"{row.speaker.first_name} {row.speaker.last_name}",
            person_id=row.speaker.person_id,
            debate=row.parent.body,
            excerpt=_plain_text(row.body),
            url=row.url,
        )


def _plain_text(markup: str) -> str:
    """Drops tags such as the search-term highlighting and decodes entities. The words are left as they are."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


class HansardSearchResult(BaseModel):
    hits: list[HansardHit]
    total_results: int = Field(description="How many speeches matched in all, including those not returned.")
    source_url: str
    licence: str


class DebateResult(BaseModel):
    gid: str
    house: Literal["representatives", "senate"]
    date: str
    debate: str = Field(description="Title of the debate.")
    url: str = Field(description="The speech or debate on OpenAustralia. Cite it.")
    text: str = Field(description="One page of the speech(es) as Hansard records them, each after the speaker's name.")
    offset: int = Field(description="Where this page starts in the full text.")
    next_offset: int | None = Field(description="Pass as offset to read the next page. None on the last page.")
    total_length: int = Field(description="Length of the full text in characters.")
    source_url: str
    licence: str

    @classmethod
    def from_entries(
        cls, entries: list[DebateEntry], gid: str, house: Literal["representatives", "senate"], offset: int
    ) -> "DebateResult":
        [requested] = [entry for entry in entries if entry.gid == gid]
        # A speech gid brings just that speech. A heading gid brings every speech under it.
        text = "\n\n".join(_speech_text(entry) for entry in entries if not entry.is_heading)
        end = offset + DEBATE_PAGE_SIZE
        return cls(
            gid=gid,
            house=house,
            date=requested.hdate,
            # Section and subsection headings, the same title getHansard gives as `parent.body`.
            debate=": ".join(entry.body for entry in entries if entry.is_heading),
            url=requested.url,
            text=text[offset:end],
            offset=offset,
            next_offset=end if len(text) > end else None,
            total_length=len(text),
            source_url=SITE_URL,
            licence=HANSARD_LICENCE,
        )


def _speech_text(entry: DebateEntry) -> str:
    """The speaker's name on its own line, then the speech, with a blank line between paragraphs."""
    text = _plain_text(re.sub(r"</p>\s*<p[^>]*>", "\n\n", entry.body)).strip()
    if entry.speaker is None:
        return text
    return f"{entry.speaker.first_name} {entry.speaker.last_name}:\n\n{text}"
