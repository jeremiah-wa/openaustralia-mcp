"""Builds the MCP server: the instructions, which span the tools, and the tools from their modules in tools/."""

import logging
from importlib.metadata import version

import httpx2
from mcp.server.mcpserver import MCPServer

from openaustralia_mcp.config import Config
from openaustralia_mcp.openaustralia import OpenAustraliaClient
from openaustralia_mcp.tools import hansard, members

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
    # The tools are listed in the order they're registered.
    members.register(server, openaustralia)
    hansard.register(server, openaustralia)
    return server
