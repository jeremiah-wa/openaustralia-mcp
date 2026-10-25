"""Builds the MCP server: tool registration, descriptions and error messages."""

from importlib.metadata import version

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from openaustralia_mcp.config import Config
from openaustralia_mcp.models import MembersResult, members_from_representatives
from openaustralia_mcp.openaustralia import OpenAustraliaClient

VERSION = version("openaustralia-mcp")

INSTRUCTIONS = """\
Answers questions about the federal Australian Parliament using OpenAustralia data.

Start with get_members to find a member and their person_id; later calls about that member use the person_id.
Every result includes a url and a licence line: cite the url when you use the data.\
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def build_server(http_client: httpx2.AsyncClient, config: Config) -> MCPServer:
    """The single construction point. Tests pass a fake HTTP client here."""
    openaustralia = OpenAustraliaClient(http_client, config.openaustralia_api_key)
    server = MCPServer("openaustralia", instructions=INSTRUCTIONS, version=VERSION)

    @server.tool(annotations=READ_ONLY)
    async def get_members(postcode: str) -> MembersResult:
        """Find the federal member of the House of Representatives (MP) for an Australian postcode.

        Returns each member's person_id, name, party, electorate and current positions. A postcode can
        span more than one electorate, so there may be several members. Senators aren't covered yet.
        """
        raw = await openaustralia.get_representatives(postcode)
        return members_from_representatives(raw)

    return server
