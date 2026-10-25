"""Smoke tests against the real APIs. Skipped unless the key env vars are set. CI runs them in live.yml."""

import os

import httpx2
import pytest
from mcp import Client

from openaustralia_mcp.config import OPENAUSTRALIA_KEY_ENV, Config
from openaustralia_mcp.server import build_server

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.environ.get(OPENAUSTRALIA_KEY_ENV), reason=f"{OPENAUSTRALIA_KEY_ENV} not set"),
]


class TestGetMembersLive:
    async def test_finds_a_member_for_a_real_postcode(self) -> None:
        async with (
            httpx2.AsyncClient(timeout=20) as http,
            Client(build_server(http, Config.from_env())) as client,
        ):
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert not result.is_error
        members = result.structured_content["members"]
        assert members
        assert all(member["person_id"] for member in members)


class TestSearchHansardLive:
    async def test_finds_speeches_by_a_real_member(self) -> None:
        async with (
            httpx2.AsyncClient(timeout=20) as http,
            Client(build_server(http, Config.from_env())) as client,
        ):
            result = await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        assert not result.is_error
        hits = result.structured_content["hits"]
        assert hits
        assert all(hit["gid"] and hit["url"].startswith("https://www.openaustralia.org.au/") for hit in hits)
