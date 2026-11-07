"""The sets of tools the evals can give Claude. See docs/evals.md#variants."""

from collections.abc import Callable

import httpx2
from mcp.server.mcpserver import MCPServer

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server

ServerFactory = Callable[[httpx2.AsyncClient, Config], MCPServer]

# "current" is the server's own tools. The others are eval-only shapes, built to compare designs before one
# goes into the server.
VARIANTS: dict[str, ServerFactory] = {"current": build_server}
