"""PROTOTYPE check: does each server get its own client when several run at once, as eval trials do?

Two servers, each with a fake API that knows only one postcode, are called at the same time, 20 rounds over. Each must
answer its own postcode, and must not find the other's: that would mean the tools reached the other server's client.
"""

import sys
from pathlib import Path

import anyio
import httpx2
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repo root, for tests.fake_api

import anyio.lowlevel

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server
from tests.fake_api import FakeApi

POSTCODES = ("3056", "3181")
results: list[str] = []


async def trial(own: str, other: str) -> None:
    fake_api = FakeApi()
    fake_api.route(f"openaustralia/getRepresentatives_postcode_{own}.json")
    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(build_server(http, Config(openaustralia_api_key="TEST-KEY-not-real"))) as client,
    ):
        for _ in range(20):
            mine = await client.call_tool("get_members", {"postcode": own})
            theirs = await client.call_tool("get_members", {"postcode": other})
            assert not mine.is_error, mine
            assert theirs.is_error, f"server for {own} answered {other}: it reached the other server's client"
            await anyio.lowlevel.checkpoint()  # let the other trial's calls interleave with this one's
        names = [member["name"] for member in mine.structured_content["members"]]
        results.append(f"server for {own}: its own postcode -> {names}; {other} -> error, as it should be")


async def main() -> None:
    async with anyio.create_task_group() as group:
        group.start_soon(trial, *POSTCODES)
        group.start_soon(trial, *reversed(POSTCODES))
    print("\n".join(sorted(results)))
    print("isolation: each server used only its own client, over 20 interleaved rounds")


anyio.run(main)
