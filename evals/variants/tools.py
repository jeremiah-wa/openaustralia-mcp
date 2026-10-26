"""Variant B for #8: more member tools, each with fewer parameters."""

from typing import Annotated

import httpx2
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from evals.variants.members import POSTCODE, MemberLookupResult, find_members
from openaustralia_mcp.config import Config
from openaustralia_mcp.openaustralia import OpenAustraliaClient
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
        return await find_members(openaustralia, postcode=postcode)

    return server
