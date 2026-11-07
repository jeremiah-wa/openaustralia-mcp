"""PROTOTYPE check: what each tool call puts on the wire, in full, to compare one prototype with another.

Run: uv run python prototype/wire_check.py out.json

It writes every tools/call result, `_meta` included, in both of the in-process Client's modes. The Resolve prototype
(chore/resolve-prototype) makes its tools "multi-round-trip tools", in the SDK docs' words. Diffing its output with
this branch's shows whether that changes anything a client receives.
"""

import json
import sys
from pathlib import Path

import anyio
import httpx2
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repo root, for tests.fake_api

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server
from tests.fake_api import FakeApi

CALLS = [
    ("get_members", {"postcode": "3056"}),
    ("get_members", {"postcode": "0000"}),  # an API error
    ("search_hansard", {"query": "housing", "person_id": "10887"}),
    ("read_debate", {"gid": "2026-06-23.80.1", "house": "representatives"}),
    ("read_debate", {"gid": "2026-06-23.80.1", "house": "representatives", "offset": 99999}),  # a ToolError
]


async def record(mode: str) -> list[dict]:
    fake_api = FakeApi()
    fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")
    fake_api.route("openaustralia/getRepresentatives_postcode_0000.json")
    fake_api.route("openaustralia/getHansard_search_housing_person_10887.json")
    fake_api.route("openaustralia/getDebates_representatives_2026-06-23.80.1.json")
    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(build_server(http, Config(openaustralia_api_key="TEST-KEY-not-real")), mode=mode) as client,
    ):
        return [
            {
                "mode": mode,
                "tool": name,
                "args": args,
                "result": (await client.call_tool(name, args)).model_dump(mode="json", by_alias=True),
            }
            for name, args in CALLS
        ]


async def main(out: Path) -> None:
    calls = [call for mode in ("auto", "legacy") for call in await record(mode)]
    out.write_text(json.dumps(calls, indent=2) + "\n", encoding="utf-8")
    print(f"{len(calls)} calls written to {out}")


anyio.run(main, Path(sys.argv[1]))
