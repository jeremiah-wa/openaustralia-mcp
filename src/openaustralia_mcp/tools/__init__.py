"""The tools, a module per family. Here, what every tool shares: its annotations and the messages for API errors.

PROTOTYPE (branch chore/context-prototype, not for main): module-level tool functions, collected by a ToolSet per
family. Each tool takes a `ctx: Context[Clients]` and reads its server's API client from the lifespan context, as in
the SDK's Lifespan docs (https://py.sdk.modelcontextprotocol.io/handlers/lifespan/).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from openaustralia_mcp.errors import (
    ApiClientError,
    ApiError,
    ApiUnavailableError,
    KeyRejectedError,
    MissingKeyError,
)
from openaustralia_mcp.openaustralia import OpenAustraliaClient

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


@dataclass(frozen=True)
class Clients:
    """One server's API clients. Its lifespan yields them, so each server built has its own. A tool that takes
    `ctx: Context[Clients]` finds them, typed, at `ctx.request_context.lifespan_context`."""

    openaustralia: OpenAustraliaClient


class ToolSet:
    """A family's tools, collected when its module is imported, for build_server to add to each server it builds."""

    def __init__(self) -> None:
        self._tools: list[Callable[..., Any]] = []

    def tool[F: Callable[..., Any]](self, fn: F) -> F:
        self._tools.append(fn)
        return fn

    def add_to(self, server: MCPServer) -> None:
        for fn in self._tools:
            # Every tool is read-only (contributing.md, house rule 4).
            server.add_tool(fn, annotations=READ_ONLY)


def _describe(exc: ApiClientError, **arguments: str | None) -> str:
    """A message Claude can relay to the user. Never includes the key or a request URL."""
    match exc:
        case MissingKeyError():
            return f"No {exc.api} key set. Get one at {exc.key_url}, then set {exc.env_var} in your MCP client config."
        case KeyRejectedError():
            return f"The {exc.api} key was rejected. Check it or get a new one at {exc.key_url}."
        case ApiError():
            args = ", ".join(f"{name}={value}" for name, value in arguments.items() if value is not None)
            return f"{exc.api} returned an error for {args}: {exc.message}"
        case ApiUnavailableError(status=None):
            return f"{exc.api} couldn't be reached. Try again later."
        case ApiUnavailableError():
            return f"{exc.api} didn't respond normally (HTTP {exc.status}). Try again later."
        case _:
            return f"{exc.api} request failed."
