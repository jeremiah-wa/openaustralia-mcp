"""What both member-lookup variants for #8 share: argument descriptions, the result, and the lookups behind them.

The variants differ only in tool names, tool descriptions and the members line of the instructions, so a
difference in their scores comes from the shape of the tools, not from what the tools return.
"""

from typing import Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from openaustralia_mcp.errors import ApiClientError
from openaustralia_mcp.openaustralia import MEMBERS_LICENCE, SITE_URL, OpenAustraliaClient, Representative

# The server's own wording, so the variants explain API errors and postcode gaps as the server does.
from openaustralia_mcp.server import PARTIAL_MATCH_NOTE, _describe

# Argument descriptions, used word for word by both variants.
POSTCODE = 'Australian postcode, e.g. "3056".'


class MemberRecord(BaseModel):
    """One person's membership of one house. Someone who sat in both houses has a record for each."""

    person_id: str = Field(description="Stable ID for this person. Pass it to other tools.")
    name: str
    party: str
    house: Literal["representatives", "senate"]
    electorate: str | None = Field(default=None, description="For a member of the House of Representatives.")
    state: str | None = Field(default=None, description="For a Senator: the state or territory they represent.")
    current: bool = Field(description="False for a former member of this house.")
    left: str | None = Field(default=None, description="The date a former member left this house.")
    positions: list[str] = Field(description="Current ministerial or other offices, if any.")
    url: str = Field(description="The member's page on OpenAustralia. Cite it.")

    @classmethod
    def from_representative(cls, representative: Representative) -> "MemberRecord":
        current = representative.is_current
        return cls(
            person_id=representative.person_id,
            name=representative.full_name,
            party=representative.party or "",
            house="representatives",
            electorate=representative.constituency,
            current=current,
            left=None if current else representative.left_house,
            # OpenAustralia attaches a person's offices to each of their records, even a former one.
            positions=representative.current_positions if current else [],
            url=representative.url,
        )


class MemberLookupResult(BaseModel):
    members: list[MemberRecord]
    note: str | None = Field(default=None, description="A caveat to pass on to the user, if any.")
    source_url: str
    licence: str


async def find_members(openaustralia: OpenAustraliaClient, *, postcode: str) -> MemberLookupResult:
    """The lookup behind every member tool in both variants."""
    try:
        representatives = await openaustralia.get_representatives(postcode)
    except ApiClientError as exc:
        raise ToolError(_describe(exc, postcode=postcode)) from None
    # A division OpenAustralia can't match to a current member comes back as `false`.
    found = [member for member in representatives if isinstance(member, Representative)]
    note = PARTIAL_MATCH_NOTE if len(found) < len(representatives) else None
    return _result([MemberRecord.from_representative(member) for member in found], note)


def _result(members: list[MemberRecord], note: str | None = None) -> MemberLookupResult:
    return MemberLookupResult(members=members, note=note, source_url=SITE_URL, licence=MEMBERS_LICENCE)
