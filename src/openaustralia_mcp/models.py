"""Tool result models: the small, citable shapes the tools return."""

from typing import Literal

from pydantic import BaseModel, Field

from openaustralia_mcp.openaustralia import Representative, Representatives

SITE_URL = "https://www.openaustralia.org.au"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
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


PARTIAL_MATCH_NOTE = (
    "OpenAustralia couldn't match part of this postcode to a current member, so this list may be incomplete. "
    "Its postcode data can lag behind changes to electorate boundaries."
)


def members_from_representatives(raw: Representatives) -> MembersResult:
    found = [member for member in raw if isinstance(member, Representative)]
    return MembersResult(
        members=[Member.from_representative(member) for member in found],
        note=PARTIAL_MATCH_NOTE if len(found) < len(raw) else None,
        source_url=SITE_URL,
        licence=MEMBERS_LICENCE,
    )
