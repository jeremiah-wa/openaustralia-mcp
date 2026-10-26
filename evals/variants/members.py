"""What both member-lookup variants for #8 share: argument descriptions, the result, and the lookups behind them.

The variants differ only in tool names, tool descriptions and the members line of the instructions, so a
difference in their scores comes from the shape of the tools, not from what the tools return.
"""

from typing import Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from openaustralia_mcp.errors import ApiClientError
from openaustralia_mcp.openaustralia import (
    MEMBERS_LICENCE,
    SITE_URL,
    OpenAustraliaClient,
    Representative,
    Senator,
    State,
)

# The server's own wording, so the variants explain API errors and postcode gaps as the server does.
from openaustralia_mcp.server import PARTIAL_MATCH_NOTE, _describe

# Argument descriptions, used word for word by both variants.
POSTCODE = 'Australian postcode, e.g. "3056".'
PERSON_ID = "A member's person_id, current or former, e.g. from a search_hansard hit."
STATE = "A state or territory, e.g. TAS. Senators represent a whole state or territory."
PARTY = 'Part of a party\'s name, e.g. "Greens" or "Labor".'


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

    @classmethod
    def from_senator(cls, senator: Senator) -> "MemberRecord":
        current = senator.is_current
        return cls(
            person_id=senator.person_id,
            name=senator.full_name,
            party=senator.party or "",
            house="senate",
            state=senator.state,
            current=current,
            left=None if current else senator.left_house,
            # Senators' records carry no offices, so a minister in the Senate shows none.
            positions=senator.current_positions if current else [],
            url=senator.url,
        )


class MemberLookupResult(BaseModel):
    members: list[MemberRecord]
    note: str | None = Field(default=None, description="A caveat to pass on to the user, if any.")
    source_url: str
    licence: str


async def by_postcode(openaustralia: OpenAustraliaClient, postcode: str) -> MemberLookupResult:
    """The MPs whose electorates cover the postcode."""
    try:
        representatives = await openaustralia.get_representatives(postcode)
    except ApiClientError as exc:
        raise ToolError(_describe(exc, postcode=postcode)) from None
    # A division OpenAustralia can't match to a current member comes back as `false`.
    found = [member for member in representatives if isinstance(member, Representative)]
    if not found:
        raise ToolError(
            f"OpenAustralia has no current member on record for postcode {postcode}. Its postcode data can lag "
            "behind changes to electorate boundaries, so try a neighbouring postcode."
        )
    note = PARTIAL_MATCH_NOTE if len(found) < len(representatives) else None
    return _result([MemberRecord.from_representative(member) for member in found], note)


async def by_person_id(openaustralia: OpenAustraliaClient, person_id: str) -> MemberLookupResult:
    """Every record the person has, in both houses: someone can move from one house to the other."""
    try:
        representative = await openaustralia.get_representative(person_id)
        senator = await openaustralia.get_senator(person_id)
    except ApiClientError as exc:
        raise ToolError(_describe(exc, person_id=person_id)) from None
    if not representative and not senator:
        raise ToolError(f"OpenAustralia has no member of either house with person_id {person_id}.")
    return _result(
        [MemberRecord.from_representative(record) for record in representative]
        + [MemberRecord.from_senator(record) for record in senator]
    )


async def search(
    openaustralia: OpenAustraliaClient, *, party: str | None = None, state: State | None = None
) -> MemberLookupResult:
    """Current members who match every filter given, in both houses unless a state limits it to the Senate."""
    given = {name: value for name, value in {"party": party, "state": state}.items() if value is not None}
    try:
        representatives = [] if state else await openaustralia.get_representatives(party=party)
        senators = await openaustralia.get_senators(state=state, party=party)
    except ApiClientError as exc:
        raise ToolError(_describe(exc, **given)) from None
    return _result(
        [MemberRecord.from_representative(member) for member in representatives if isinstance(member, Representative)]
        + [MemberRecord.from_senator(senator) for senator in senators]
    )


def _result(members: list[MemberRecord], note: str | None = None) -> MemberLookupResult:
    return MemberLookupResult(members=members, note=note, source_url=SITE_URL, licence=MEMBERS_LICENCE)
