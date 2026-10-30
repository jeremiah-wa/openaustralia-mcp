"""Smoke tests against the real APIs. Skipped unless the key env vars are set. CI runs them in live.yml."""

import os

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult

from openaustralia_mcp.config import OPENAUSTRALIA_KEY_ENV, Config
from openaustralia_mcp.server import build_server

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.environ.get(OPENAUSTRALIA_KEY_ENV), reason=f"{OPENAUSTRALIA_KEY_ENV} not set"),
]


async def get_members(args: dict[str, str]) -> CallToolResult:
    async with (
        httpx2.AsyncClient(timeout=20) as http,
        Client(build_server(http, Config.from_env())) as client,
    ):
        return await client.call_tool("get_members", args)


class TestGetMembersLive:
    async def test_finds_a_former_member_by_person_id(self) -> None:
        result = await get_members({"person_id": "10990"})

        assert not result.is_error
        [member] = result.structured_content["members"]
        assert member["name"] == "Keith Wolahan"
        assert member["current"] is False

    async def test_finds_both_records_of_someone_who_moved_houses(self) -> None:
        result = await get_members({"person_id": "10942"})

        assert not result.is_error
        assert {member["house"] for member in result.structured_content["members"]} == {"representatives", "senate"}

    @pytest.mark.parametrize("state", ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"])
    async def test_lists_each_states_senators(self, state: str) -> None:
        # OpenAustralia spells states inconsistently, and only a real call shows a spelling still works.
        result = await get_members({"state": state})

        assert not result.is_error
        assert {member["state"] for member in result.structured_content["members"]} == {state}

    async def test_finds_a_partys_members_in_both_houses(self) -> None:
        result = await get_members({"party": "Labor"})

        assert not result.is_error
        assert {member["house"] for member in result.structured_content["members"]} == {"representatives", "senate"}

    async def test_finds_a_member_by_name(self) -> None:
        result = await get_members({"name": "Khalil"})

        assert not result.is_error
        assert "Peter Khalil" in [member["name"] for member in result.structured_content["members"]]

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


class TestReadDebateLive:
    async def test_reads_a_speech_found_by_search_hansard(self) -> None:
        async with (
            httpx2.AsyncClient(timeout=20) as http,
            Client(build_server(http, Config.from_env())) as client,
        ):
            search = await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})
            hit = search.structured_content["hits"][0]
            result = await client.call_tool("read_debate", {"gid": hit["gid"], "house": hit["house"]})

        assert not result.is_error
        content = result.structured_content
        assert content["text"].startswith(f"{hit['speaker']}:\n\n")
        assert content["debate"] == hit["debate"]
