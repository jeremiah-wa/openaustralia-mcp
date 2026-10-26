"""The sets of tools the evals can give Claude. See docs/evals.md#variants."""

from collections.abc import Callable

import httpx2
from mcp.server.mcpserver import MCPServer

from evals.variants.parameters import build_parameters_server
from evals.variants.tools import build_tools_server
from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server

ServerFactory = Callable[[httpx2.AsyncClient, Config], MCPServer]

# "current" is the server's own tools. The others are eval-only shapes, built to compare designs before one
# goes into the server: for #8, more parameters on one member tool, or more member tools.
VARIANTS: dict[str, ServerFactory] = {
    "current": build_server,
    "parameters": build_parameters_server,
    "tools": build_tools_server,
}
