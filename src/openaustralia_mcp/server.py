"""Builds the MCP server: tool registration, descriptions and error messages."""

import logging
from importlib.metadata import version
from typing import Annotated

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from openaustralia_mcp.config import Config
from openaustralia_mcp.errors import ApiClientError, NotFoundError
from openaustralia_mcp.models import DebateResult, HansardSearchResult
from openaustralia_mcp.openaustralia import House, OpenAustraliaClient
from openaustralia_mcp.tools import READ_ONLY, _describe, members

VERSION = version("openaustralia-mcp")

INSTRUCTIONS = """\
Answers questions about the federal Australian Parliament using OpenAustralia data.

Start with get_members to find a member and their person_id, by postcode, name, party or state, \
or to look up a person_id; later calls about that member use the person_id.
To find what a member said in Parliament, pass their person_id to search_hansard, with or without a query.
To read a speech in full, pass a hit's gid and house to read_debate; follow next_offset for more.
Every result includes a url and a licence line: cite the url when you use the data.
Hansard excerpts are Commonwealth copyright (no derivatives): quote them as they are, and summarise in your own words.\
"""

# The HTTP library logs every request URL at INFO and below, and the URL contains the API key.
HTTP_LOGGERS = ("httpx2", "httpcore2")


def build_server(http_client: httpx2.AsyncClient, config: Config) -> MCPServer:
    """The single construction point. Tests pass a fake HTTP client here."""
    for name in HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    openaustralia = OpenAustraliaClient(http_client, config.openaustralia_api_key)
    server = MCPServer("openaustralia", instructions=INSTRUCTIONS, version=VERSION)
    members.register(server, openaustralia)

    @server.tool(annotations=READ_ONLY)
    async def search_hansard(
        query: Annotated[
            str | None, Field(min_length=1, description='Words to search for, e.g. "housing affordability".')
        ] = None,
        person_id: Annotated[
            str | None,
            Field(pattern=r"^\d+$", description="Only speeches by this member. Get it from get_members."),
        ] = None,
    ) -> HansardSearchResult:
        """Search what was said in federal Parliament (Hansard), in both the House and the Senate.

        Returns the 20 most recent matching speeches, each with the speaker, date, debate title, a short
        excerpt, a gid and a url to the full speech.
        """
        if query is None and person_id is None:
            raise ToolError("Give a query, a person_id, or both.")
        try:
            search = await openaustralia.search_hansard(query, person_id)
        except ApiClientError as exc:
            raise ToolError(_describe(exc, query=query, person_id=person_id)) from None
        return HansardSearchResult.from_search(search)

    @server.tool(annotations=READ_ONLY)
    async def read_debate(
        gid: Annotated[
            str,
            Field(
                pattern=r"^\d{4}-\d{2}-\d{2}\.\d+\.\d+$",
                description="A speech's gid, from search_hansard. Or, to read the whole debate, the id= in its url.",
            ),
        ],
        house: Annotated[
            House,
            Field(description="The house the gid is from, as search_hansard gives it. gids repeat across houses."),
        ],
        offset: Annotated[
            int, Field(ge=0, description="Where to start reading. Pass next_offset from the last call.")
        ] = 0,
    ) -> DebateResult:
        """Read the full text of a speech or debate in federal Parliament (Hansard), by its gid and house.

        Each speech starts with the speaker's name on its own line. Returns up to 4,000 characters at a
        time. Pass next_offset as offset to read on.
        """
        try:
            entries = await openaustralia.get_debates(house, gid)
        except NotFoundError:
            raise ToolError(
                f"OpenAustralia has no speech or debate with gid {gid} in the {house}. "
                "Check that house matches the search_hansard hit the gid came from."
            ) from None
        except ApiClientError as exc:
            raise ToolError(_describe(exc, gid=gid, house=house)) from None
        result = DebateResult.from_entries(entries, gid, house, offset)
        if offset > 0 and offset >= result.total_length:
            raise ToolError(
                f"offset {offset} is past the end of the text, which is {result.total_length} characters long. "
                "Start from 0, or pass next_offset from the last call."
            )
        return result

    return server
