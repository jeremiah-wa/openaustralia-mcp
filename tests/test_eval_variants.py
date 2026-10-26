"""The member-lookup variants for #8, through the tool call, as Claude uses them (see docs/evals.md#variants).

Each test runs the same lookup on both variants and expects the same result: the variants may differ only in what
Claude sees, never in what it gets back.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult

from evals.variants import VARIANTS

from .conftest import TEST_CONFIG, result_text
from .fake_api import FakeApi

pytestmark = pytest.mark.anyio

SOURCE_URL = "https://www.openaustralia.org.au"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
)


@asynccontextmanager
async def connect(variant: str, fake_api: FakeApi) -> AsyncGenerator[Client, None]:
    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(VARIANTS[variant](http, TEST_CONFIG)) as client,
    ):
        yield client


async def call(fake_api: FakeApi, variant: str, tool: str, args: dict[str, Any]) -> CallToolResult:
    async with connect(variant, fake_api) as client:
        return await client.call_tool(tool, args)


class TestByPostcode:
    LOOKUPS = (("parameters", "get_members"), ("tools", "get_members"))

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_returns_the_member_with_attribution(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")

        result = await call(fake_api, variant, tool, {"postcode": "3056"})

        assert not result.is_error
        assert result.structured_content == {
            "members": [
                {
                    "person_id": "10887",
                    "name": "Peter Khalil",
                    "party": "Australian Labor Party",
                    "house": "representatives",
                    "electorate": "Wills",
                    "state": None,
                    "current": True,
                    "left": None,
                    "positions": ["Assistant Minister for Defence"],
                    "url": "https://www.openaustralia.org.au/mp/?p=10887",
                }
            ],
            "note": None,
            "source_url": SOURCE_URL,
            "licence": MEMBERS_LICENCE,
        }

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_notes_a_division_with_no_current_member(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        # 3181 spans Higgins, abolished in 2025, and Macnamara: OpenAustralia sends [false, Josh Burns].
        fake_api.route("openaustralia/getRepresentatives_postcode_3181.json")

        result = await call(fake_api, variant, tool, {"postcode": "3181"})

        assert [member["name"] for member in result.structured_content["members"]] == ["Josh Burns"]
        assert result.structured_content["note"] == (
            "OpenAustralia couldn't match part of this postcode to a current member, so this list may be "
            "incomplete. Its postcode data can lag behind changes to electorate boundaries."
        )

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_suggests_a_neighbour_when_no_member_is_current(
        self, fake_api: FakeApi, variant: str, tool: str
    ) -> None:
        # 3142 is all Higgins: OpenAustralia sends [false].
        fake_api.route("openaustralia/getRepresentatives_postcode_3142.json")

        result = await call(fake_api, variant, tool, {"postcode": "3142"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia has no current member on record for postcode 3142. "
            "Its postcode data can lag behind changes to electorate boundaries, so try a neighbouring postcode."
        )
