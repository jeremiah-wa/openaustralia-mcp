"""Variant A for #8: one member tool, with more parameters."""

from typing import Annotated

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from evals.variants.members import PERSON_ID, POSTCODE, MemberLookupResult, by_person_id, by_postcode
from openaustralia_mcp.config import Config
from openaustralia_mcp.openaustralia import OpenAustraliaClient
from openaustralia_mcp.server import READ_ONLY, build_server


def build_parameters_server(http_client: httpx2.AsyncClient, config: Config) -> MCPServer:
    """The server's own tools, with get_members replaced."""
    server = build_server(http_client, config)
    server.remove_tool("get_members")
    openaustralia = OpenAustraliaClient(http_client, config.openaustralia_api_key)

    @server.tool(annotations=READ_ONLY)
    async def get_members(
        postcode: Annotated[str | None, Field(pattern=r"^\d{4}$", description=POSTCODE)] = None,
        person_id: Annotated[str | None, Field(pattern=r"^\d+$", description=PERSON_ID)] = None,
    ) -> MemberLookupResult:
        """Find federal members of Parliament.

        By postcode, it finds the members of the House of Representatives (MPs) for that area. A postcode can
        span more than one electorate, so there may be several. By person_id, it finds one person, current or
        former, in either house. Returns each member's person_id, name, party, house, electorate or state,
        whether they're a current member, current positions and url.
        """
        if person_id is not None:
            return await by_person_id(openaustralia, person_id)
        if postcode is not None:
            return await by_postcode(openaustralia, postcode)
        raise ToolError("Give a postcode or a person_id.")

    return server
