"""Tool result models: the small, citable shapes the tools return."""

import html
import re
from typing import Literal

from pydantic import BaseModel, Field

from openaustralia_mcp.openaustralia import HansardRow, Representative

SITE_URL = "https://www.openaustralia.org.au"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
)
HANSARD_LICENCE = (
    "Hansard: Commonwealth of Australia, CC BY-NC-ND 3.0 AU (https://creativecommons.org/licenses/by-nc-nd/3.0/au/)"
)


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
            url=f"{SITE_URL}/mp/?p={representative.person_id}",
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
            # listurl is relative and HTML-escaped (`&amp;`).
            url=SITE_URL + html.unescape(row.listurl),
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
    source_url: str
    licence: str
