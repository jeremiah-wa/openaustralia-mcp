"""Writes what Claude sees of the server, list_tools() and the instructions, as JSON to the path given."""

import json
import sys
from pathlib import Path

import anyio
import httpx2
from mcp import Client

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server


async def main(out: Path) -> None:
    async with (
        httpx2.AsyncClient() as http,
        Client(build_server(http, Config(openaustralia_api_key="unused"))) as client,
    ):
        tools = (await client.list_tools()).tools
        snapshot = {
            "instructions": client.instructions,
            "tools": [tool.model_dump(mode="json", by_alias=True) for tool in tools],
        }
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n", encoding="utf-8")


anyio.run(main, Path(sys.argv[1]))
