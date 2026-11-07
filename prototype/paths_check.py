"""PROTOTYPE check: does the resolver get its server's client on every path a client can connect by?

1. In process, in both of the Client's modes: "auto" (the modern per-request path, which the tests use) and "legacy"
   (the stream loop, as over stdio). Each calls all three tools.
2. The real entry point over stdio, with the key set empty, so no request leaves the machine. get_members has to go
   through the lifespan and the resolver to reach the client, which then says no key is set.
"""

import sys
from pathlib import Path

import anyio
import httpx2
from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # for tests.fake_api

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server
from tests.fake_api import FakeApi

CALLS = [
    ("get_members", {"postcode": "3056"}),
    ("search_hansard", {"query": "housing", "person_id": "10887"}),
    ("read_debate", {"gid": "2026-06-23.80.1", "house": "representatives"}),
]


def summary(result) -> str:
    if result.is_error:
        return f"ERROR {result.content[0].text}"
    content = result.structured_content
    if "members" in content:
        return f"members={[member['name'] for member in content['members']]}"
    if "hits" in content:
        return f"{len(content['hits'])} hits of {content['total_results']}"
    return f"debate={content['debate'][:50]!r}, {content['total_length']} characters"


async def in_process(mode: str) -> None:
    fake_api = FakeApi()
    fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")
    fake_api.route("openaustralia/getHansard_search_housing_person_10887.json")
    fake_api.route("openaustralia/getDebates_representatives_2026-06-23.80.1.json")
    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(build_server(http, Config(openaustralia_api_key="TEST-KEY-not-real")), mode=mode) as client,
    ):
        for name, args in CALLS:
            print(f"  [{mode}] {name}: {summary(await client.call_tool(name, args))}")


async def over_stdio() -> None:
    params = StdioServerParameters(command="openaustralia-mcp", env={"OPENAUSTRALIA_API_KEY": ""}, cwd=REPO)
    async with Client(stdio_client(params)) as client:
        tools = [tool.name for tool in (await client.list_tools()).tools]
        print(f"  [stdio] tools: {tools}")
        print(f"  [stdio] get_members: {summary(await client.call_tool('get_members', {'postcode': '3056'}))}")


async def main() -> None:
    print("in process:")
    for mode in ("auto", "legacy"):
        await in_process(mode)
    print("over stdio, the real entry point:")
    await over_stdio()


anyio.run(main)
