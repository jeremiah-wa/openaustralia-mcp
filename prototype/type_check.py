"""PROTOTYPE check: does `ctx: Context[Clients]` give a type checker the client's type, as the SDK's Lifespan docs say?

Run: uv run --with mypy mypy --follow-imports=silent prototype/type_check.py

mypy should reveal OpenAustraliaClient on the first line, and report the misspelt attribute on the second.
"""

from typing import reveal_type

from mcp.server.mcpserver import Context

from openaustralia_mcp.tools import Clients


def reads_the_client(ctx: Context[Clients]) -> None:
    reveal_type(ctx.request_context.lifespan_context.openaustralia)
    _ = ctx.request_context.lifespan_context.openaustrlia  # misspelt on purpose
