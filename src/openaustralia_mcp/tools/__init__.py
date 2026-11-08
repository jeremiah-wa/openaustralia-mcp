"""The tools, a module per family.

Here, what every tool shares: its server's API clients, its annotations and the messages for API errors.
"""

from dataclasses import dataclass

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
    """One server's API clients. Its lifespan yields them, so each server that build_server makes has its own."""

    openaustralia: OpenAustraliaClient


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
