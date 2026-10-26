"""Variant B for #8: more member tools, each with fewer parameters."""

from typing import Annotated

import httpx2
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from evals.variants.members import (
    PARTY,
    PERSON_ID,
    POSTCODE,
    STATE,
    MemberLookupResult,
    by_person_id,
    by_postcode,
    search,
)
from openaustralia_mcp.config import Config
from openaustralia_mcp.openaustralia import OpenAustraliaClient, State
from openaustralia_mcp.server import READ_ONLY, build_server


def build_tools_server(http_client: httpx2.AsyncClient, config: Config) -> MCPServer:
    """The server's own tools, with get_members replaced."""
    server = build_server(http_client, config)
    server.remove_tool("get_members")
    openaustralia = OpenAustraliaClient(http_client, config.openaustralia_api_key)

    @server.tool(annotations=READ_ONLY)
    async def get_members(
        postcode: Annotated[str, Field(pattern=r"^\d{4}$", description=POSTCODE)],
    ) -> MemberLookupResult:
        """Find the federal members of the House of Representatives (MPs) for an Australian postcode.

        A postcode can span more than one electorate, so there may be several. Returns each member's person_id,
        name, party, house, electorate or state, whether they're a current member, current positions and url.
        """
        return await by_postcode(openaustralia, postcode)

    @server.tool(annotations=READ_ONLY)
    async def get_member(
        person_id: Annotated[str, Field(pattern=r"^\d+$", description=PERSON_ID)],
    ) -> MemberLookupResult:
        """Find one federal member of Parliament by person_id, current or former, in either house.

        Returns the person's records: name, party, house, electorate or state, whether they're a current member,
        current positions and url. Someone who moved between houses has a record for each.
        """
        return await by_person_id(openaustralia, person_id)

    @server.tool(annotations=READ_ONLY)
    async def get_senators(
        state: Annotated[State | None, Field(description=STATE)] = None,
        party: Annotated[str | None, Field(min_length=2, description=PARTY)] = None,
    ) -> MemberLookupResult:
        """List current Senators, for one state or territory and of one party, if given.

        Returns each Senator's person_id, name, party, house, state, whether they're a current member, current
        positions and url.
        """
        return await search(openaustralia, state=state, party=party, house="senate")

    @server.tool(annotations=READ_ONLY)
    async def search_members(
        party: Annotated[str | None, Field(min_length=2, description=PARTY)] = None,
    ) -> MemberLookupResult:
        """Find current federal members of Parliament in both houses, by party.

        Returns each member's person_id, name, party, house, electorate or state, whether they're a current
        member, current positions and url.
        """
        return await search(openaustralia, party=party)

    return server
