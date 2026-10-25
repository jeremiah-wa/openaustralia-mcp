"""Builds the MCP server: tool registration, descriptions and error messages."""

import logging
from importlib.metadata import version
from typing import Annotated

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from openaustralia_mcp.config import Config
from openaustralia_mcp.errors import (
    ApiClientError,
    ApiError,
    ApiUnavailableError,
    KeyRejectedError,
    MissingKeyError,
)
from openaustralia_mcp.models import MembersResult, members_from_representatives
from openaustralia_mcp.openaustralia import OpenAustraliaClient

VERSION = version("openaustralia-mcp")

INSTRUCTIONS = """\
Answers questions about the federal Australian Parliament using OpenAustralia data.

Start with get_members to find a member and their person_id; later calls about that member use the person_id.
Every result includes a url and a licence line: cite the url when you use the data.\
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

# The HTTP library logs every request URL at INFO and below, and the URL contains the API key.
HTTP_LOGGERS = ("httpx2", "httpcore2")


def build_server(http_client: httpx2.AsyncClient, config: Config) -> MCPServer:
    """The single construction point. Tests pass a fake HTTP client here."""
    for name in HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    openaustralia = OpenAustraliaClient(http_client, config.openaustralia_api_key)
    server = MCPServer("openaustralia", instructions=INSTRUCTIONS, version=VERSION)

    @server.tool(annotations=READ_ONLY)
    async def get_members(
        postcode: Annotated[str, Field(pattern=r"^\d{4}$", description='Australian postcode, e.g. "3056".')],
    ) -> MembersResult:
        """Find the federal member of the House of Representatives (MP) for an Australian postcode.

        Returns each member's person_id, name, party, electorate and current positions. A postcode can
        span more than one electorate, so there may be several members. Senators aren't covered yet.
        """
        try:
            raw = await openaustralia.get_representatives(postcode)
        except ApiClientError as exc:
            raise ToolError(_describe(exc, postcode=postcode)) from None
        result = members_from_representatives(raw)
        if not result.members:
            raise ToolError(
                f"OpenAustralia has no current member on record for postcode {postcode}. Its postcode data can lag "
                "behind changes to electorate boundaries, so try a neighbouring postcode."
            )
        return result

    return server


def _describe(exc: ApiClientError, **arguments: str) -> str:
    """A message Claude can relay to the user. Never includes the key or a request URL."""
    match exc:
        case MissingKeyError():
            return f"No {exc.api} key set. Get one at {exc.key_url}, then set {exc.env_var} in your MCP client config."
        case KeyRejectedError():
            return f"The {exc.api} key was rejected. Check it or get a new one at {exc.key_url}."
        case ApiError():
            args = ", ".join(f"{name}={value}" for name, value in arguments.items())
            return f"{exc.api} returned an error for {args}: {exc.message}"
        case ApiUnavailableError(status=None):
            return f"{exc.api} couldn't be reached. Try again later."
        case ApiUnavailableError():
            return f"{exc.api} didn't respond normally (HTTP {exc.status}). Try again later."
        case _:
            return f"{exc.api} request failed."
