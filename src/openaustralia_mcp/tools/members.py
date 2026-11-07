"""get_members: federal members of Parliament, and the shape of their records."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from openaustralia_mcp.errors import ApiClientError
from openaustralia_mcp.openaustralia import (
    MEMBERS_LICENCE,
    SITE_URL,
    House,
    OpenAustraliaClient,
    Representative,
    Senator,
    State,
)
from openaustralia_mcp.tools import READ_ONLY, _describe

PARTIAL_MATCH_NOTE = (
    "OpenAustralia couldn't match part of this postcode to a current member, so this list may be incomplete. "
    "Its postcode data can lag behind changes to electorate boundaries."
)


class MemberRecord(BaseModel):
    """One person's membership of one house. Someone who sat in both houses has a record for each."""

    person_id: str = Field(description="Stable ID for this person. Pass it to other tools.")
    name: str
    party: str
    house: House
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
            # A person's offices belong on their current record, as for a Representative.
            positions=senator.current_positions if current else [],
            url=senator.url,
        )


class MemberLookupResult(BaseModel):
    members: list[MemberRecord]
    note: str | None = Field(default=None, description="A caveat to pass on to the user, if any.")
    source_url: str
    licence: str

    @classmethod
    def from_members(cls, members: list[MemberRecord], note: str | None = None) -> "MemberLookupResult":
        return cls(members=members, note=note, source_url=SITE_URL, licence=MEMBERS_LICENCE)


def register(server: MCPServer, openaustralia: OpenAustraliaClient) -> None:
    @server.tool(annotations=READ_ONLY)
    async def get_members(
        postcode: Annotated[
            str | None, Field(pattern=r"^\d{4}$", description='Australian postcode, e.g. "3056".')
        ] = None,
        person_id: Annotated[
            str | None,
            Field(
                pattern=r"^\d+$",
                description="A member's person_id, current or former, e.g. from a search_hansard hit.",
            ),
        ] = None,
        name: Annotated[
            str | None,
            Field(
                min_length=2,
                description='Part or all of a current member\'s name, e.g. "Khalil" or "Peter Khalil", without a title.',
            ),
        ] = None,
        party: Annotated[
            str | None, Field(min_length=2, description='Part of a party\'s name, e.g. "Greens" or "Labor".')
        ] = None,
        state: Annotated[
            State | None,
            Field(description="A state or territory, e.g. TAS. Senators represent a whole state or territory."),
        ] = None,
        house: Annotated[
            House | None,
            Field(description="Only members of this house: the House of Representatives (MPs) or the Senate."),
        ] = None,
    ) -> MemberLookupResult:
        """Find federal members of Parliament.

        By postcode, it finds the members of the House of Representatives (MPs) for that area. A postcode can
        span more than one electorate, so there may be several. By person_id, it finds one person, current or
        former, in either house. By name, party or state, it finds current members who match all of them, in
        both houses unless house limits it to one. A state means Senators. Returns each member's person_id, name,
        party, house, electorate or state, whether they're a current member, current positions and url.
        """
        if person_id is not None:
            if any(value is not None for value in (postcode, name, party, state, house)):
                raise ToolError("A person_id finds one person in both houses by itself. Give it on its own.")
            return await _member_by_person_id(openaustralia, person_id)
        if postcode is not None:
            if any(value is not None for value in (name, party, state)) or house == "senate":
                raise ToolError(
                    "A postcode finds the MPs for that area by itself. Give it on its own, "
                    "or search by name, party, state and house instead."
                )
            return await _members_by_postcode(openaustralia, postcode)
        if state is not None and house == "representatives":
            raise ToolError(
                "A state means Senators: they represent a whole state or territory. "
                "MPs represent electorates, so for MPs give a postcode or a name instead."
            )
        if any(value is not None for value in (name, party, state, house)):
            return await _search_members(openaustralia, name=name, party=party, state=state, house=house)
        raise ToolError("Give a postcode, a person_id, or any of name, party, state and house.")


async def _members_by_postcode(openaustralia: OpenAustraliaClient, postcode: str) -> MemberLookupResult:
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
    return MemberLookupResult.from_members([MemberRecord.from_representative(member) for member in found], note)


async def _member_by_person_id(openaustralia: OpenAustraliaClient, person_id: str) -> MemberLookupResult:
    """Every record the person has, in both houses: someone can move from one house to the other."""
    try:
        representative = await openaustralia.get_representative(person_id)
        senator = await _with_offices(openaustralia, await openaustralia.get_senator(person_id))
    except ApiClientError as exc:
        raise ToolError(_describe(exc, person_id=person_id)) from None
    if not representative and not senator:
        raise ToolError(f"OpenAustralia has no member of either house with person_id {person_id}.")
    return MemberLookupResult.from_members(
        [MemberRecord.from_representative(record) for record in representative]
        + [MemberRecord.from_senator(record) for record in senator]
    )


async def _with_offices(openaustralia: OpenAustraliaClient, records: list[Senator]) -> list[Senator]:
    """The same records with their offices: getSenator sends none, and getSenators does."""
    if not any(record.is_current for record in records):
        return records
    listed = {senator.person_id: senator for senator in await openaustralia.get_senators()}
    return [listed.get(record.person_id, record) if record.is_current else record for record in records]


async def _search_members(
    openaustralia: OpenAustraliaClient,
    *,
    name: str | None = None,
    party: str | None = None,
    state: State | None = None,
    house: House | None = None,
) -> MemberLookupResult:
    """Current members who match every filter given, in both houses unless a house or a state limits it."""
    filters = {"name": name, "party": party, "state": state, "house": house}
    # Senators represent a state. Members of the House represent an electorate, and OpenAustralia has no state for it.
    house = "senate" if state else house
    try:
        representatives = [] if house == "senate" else await openaustralia.get_representatives(party=party, search=name)
        senators = (
            []
            if house == "representatives"
            else await openaustralia.get_senators(state=state, party=party, search=name)
        )
    except ApiClientError as exc:
        raise ToolError(_describe(exc, **filters)) from None
    members = [
        MemberRecord.from_representative(member) for member in representatives if isinstance(member, Representative)
    ] + [MemberRecord.from_senator(senator) for senator in senators]
    if not members:
        matching = ", ".join(f"{key}={value}" for key, value in filters.items() if value is not None)
        raise ToolError(
            f"OpenAustralia has no current member matching {matching}. Searches find current members only. "
            "For a former member, find their person_id, for example on a search_hansard hit, and look them up by that."
        )
    return MemberLookupResult.from_members(members)
