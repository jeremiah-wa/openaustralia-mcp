"""Builds the MCP server: tool registration, descriptions and error messages."""

import logging
from importlib.metadata import version
from typing import Annotated, Literal

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
from openaustralia_mcp.models import (
    HANSARD_LICENCE,
    MEMBERS_LICENCE,
    SITE_URL,
    DebateResult,
    HansardHit,
    HansardSearchResult,
    Member,
    MembersResult,
)
from openaustralia_mcp.openaustralia import OpenAustraliaClient, Representative

VERSION = version("openaustralia-mcp")

INSTRUCTIONS = """\
Answers questions about the federal Australian Parliament using OpenAustralia data.

Start with get_members to find a member and their person_id; later calls about that member use the person_id.
To find what a member said in Parliament, pass their person_id to search_hansard, with or without a query.
Every result includes a url and a licence line: cite the url when you use the data.
Hansard excerpts are Commonwealth copyright (no derivatives): quote them as they are, and summarise in your own words.\
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

# The HTTP library logs every request URL at INFO and below, and the URL contains the API key.
HTTP_LOGGERS = ("httpx2", "httpcore2")

PARTIAL_MATCH_NOTE = (
    "OpenAustralia couldn't match part of this postcode to a current member, so this list may be incomplete. "
    "Its postcode data can lag behind changes to electorate boundaries."
)


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
        return MembersResult(
            members=[Member.from_representative(member) for member in found],
            note=PARTIAL_MATCH_NOTE if len(found) < len(representatives) else None,
            source_url=SITE_URL,
            licence=MEMBERS_LICENCE,
        )

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
            given = {"query": query, "person_id": person_id}
            raise ToolError(
                _describe(exc, **{name: value for name, value in given.items() if value is not None})
            ) from None
        return HansardSearchResult(
            hits=[HansardHit.from_row(row) for row in search.rows],
            total_results=search.info.total_results,
            source_url=SITE_URL,
            licence=HANSARD_LICENCE,
        )

    @server.tool(annotations=READ_ONLY)
    async def read_debate(
        gid: Annotated[
            str,
            Field(description="A speech's gid, from search_hansard. Or, to read the whole debate, the id= in its url."),
        ],
        house: Annotated[
            Literal["representatives", "senate"],
            Field(description="The house the gid is from, as search_hansard gives it. gids repeat across houses."),
        ],
        offset: Annotated[int, Field(description="Where to start reading. Pass next_offset from the last call.")] = 0,
    ) -> DebateResult:
        """Read the full text of a speech or debate in federal Parliament (Hansard), by its gid and house.

        Each speech starts with the speaker's name on its own line. Returns up to 4,000 characters at a
        time. Pass next_offset as offset to read on.
        """
        try:
            entries = await openaustralia.get_debates(house, gid)
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
