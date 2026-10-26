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


class TestByPersonId:
    LOOKUPS = (("parameters", "get_members"), ("tools", "get_member"))

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_finds_a_former_member(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        # Keith Wolahan was the MP for Menzies until 2025, and was never a Senator.
        fake_api.route("openaustralia/getRepresentative_id_10990.json")
        fake_api.route("openaustralia/getSenator_id_10990.json")

        result = await call(fake_api, variant, tool, {"person_id": "10990"})

        assert not result.is_error
        assert result.structured_content == {
            "members": [
                {
                    "person_id": "10990",
                    "name": "Keith Wolahan",
                    "party": "Liberal Party",
                    "house": "representatives",
                    "electorate": "Menzies",
                    "state": None,
                    "current": False,
                    "left": "2025-05-03",
                    "positions": [],
                    "url": "https://www.openaustralia.org.au/mp/?p=10990",
                }
            ],
            "note": None,
            "source_url": SOURCE_URL,
            "licence": MEMBERS_LICENCE,
        }

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_finds_someone_who_moved_houses(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        # Dave Sharma was the MP for Wentworth until 2022, and has been a Senator for NSW since 2023.
        fake_api.route("openaustralia/getRepresentative_id_10942.json")
        fake_api.route("openaustralia/getSenator_id_10942.json")

        result = await call(fake_api, variant, tool, {"person_id": "10942"})

        assert not result.is_error
        assert result.structured_content["members"] == [
            {
                "person_id": "10942",
                "name": "Dave Sharma",
                "party": "Liberal Party",
                "house": "representatives",
                "electorate": "Wentworth",
                "state": None,
                "current": False,
                "left": "2022-05-21",
                "positions": [],
                "url": "https://www.openaustralia.org.au/mp/?p=10942",
            },
            {
                "person_id": "10942",
                "name": "Dave Sharma",
                "party": "Liberal Party",
                "house": "senate",
                "electorate": None,
                "state": "NSW",
                "current": True,
                "left": None,
                "positions": [],
                "url": "https://www.openaustralia.org.au/senator/?p=10942",
            },
        ]

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_says_when_neither_house_knows_the_person(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        fake_api.route("openaustralia/getRepresentative_id_99999.json")
        fake_api.route("openaustralia/getSenator_id_99999.json")

        result = await call(fake_api, variant, tool, {"person_id": "99999"})

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {tool}: OpenAustralia has no member of either house with person_id 99999."
        )

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_asks_both_houses(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        fake_api.route("openaustralia/getRepresentative_id_10990.json")
        fake_api.route("openaustralia/getSenator_id_10990.json")

        await call(fake_api, variant, tool, {"person_id": "10990"})

        asked = {(request.url.path.rsplit("/", 1)[-1], request.url.params["id"]) for request in fake_api.requests}
        assert asked == {("getRepresentative", "10990"), ("getSenator", "10990")}


# The current Senators for Tasmania, in the order OpenAustralia sends them.
TASMANIA = [
    "Carol Brown",
    "Helen Polley",
    "Nick McKim",
    "Jonathon Duniam",
    "Richard Colbeck",
    "Claire Chandler",
    "Jacqui Lambie",
    "Josh Dolega",
    "Richard Dowling",
    "Tammy Tyrrell",
    "Chris Gatenby",
    "Vanessa Bleyer",
]


class TestSenatorsByState:
    LOOKUPS = (("parameters", "get_members"), ("tools", "get_senators"))

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_lists_the_states_senators(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        # OpenAustralia takes TAS or Tasmania. The tools send Tasmania, the only fixture recorded.
        fake_api.route("openaustralia/getSenators_state_Tasmania.json")

        result = await call(fake_api, variant, tool, {"state": "TAS"})

        assert not result.is_error
        members = result.structured_content["members"]
        assert [member["name"] for member in members] == TASMANIA
        assert members[-1] == {
            "person_id": "11065",
            "name": "Vanessa Bleyer",
            "party": "Australian Greens",
            "house": "senate",
            "electorate": None,
            "state": "TAS",
            "current": True,
            "left": None,
            "positions": [],
            "url": "https://www.openaustralia.org.au/senator/?p=11065",
        }


# The current Greens Senators, in the order OpenAustralia sends them.
GREENS_SENATORS = [
    "Sarah Hanson-Young",
    "Nick McKim",
    "Jordon Steele-John",
    "Mehreen Faruqi",
    "Larissa Waters",
    "Penny Allman-Payne",
    "Barbara Pocock",
    "David Shoebridge",
    "Steph Hodgins-May",
    "Vanessa Bleyer",
]


class TestByParty:
    LOOKUPS = (("parameters", "get_members"), ("tools", "search_members"))

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_finds_the_partys_members_in_both_houses(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        fake_api.route("openaustralia/getRepresentatives_party_Greens.json", part_of={"party": ["Australian Greens"]})
        fake_api.route("openaustralia/getSenators_party_Greens.json", part_of={"party": ["Australian Greens"]})

        result = await call(fake_api, variant, tool, {"party": "Greens"})

        assert not result.is_error
        members = result.structured_content["members"]
        assert [(member["name"], member["house"]) for member in members] == [
            ("Elizabeth Watson-Brown", "representatives"),
            *((name, "senate") for name in GREENS_SENATORS),
        ]
        assert members[0]["electorate"] == "Ryan"

    @pytest.mark.parametrize(
        ("variant", "tool", "args"),
        [
            ("parameters", "get_members", {"party": "Greens", "house": "senate"}),
            ("tools", "get_senators", {"party": "Greens"}),
        ],
    )
    async def test_finds_the_partys_senators(
        self, fake_api: FakeApi, variant: str, tool: str, args: dict[str, str]
    ) -> None:
        # Only the Senate is recorded, so asking the House as well would fail.
        fake_api.route("openaustralia/getSenators_party_Greens.json", part_of={"party": ["Australian Greens"]})

        result = await call(fake_api, variant, tool, args)

        assert not result.is_error
        assert [member["name"] for member in result.structured_content["members"]] == GREENS_SENATORS


class TestByName:
    LOOKUPS = (("parameters", "get_members"), ("tools", "search_members"))

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_finds_current_members_in_both_houses(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        # No MP is called Pocock, so getRepresentatives sends `{}`. Two Senators are.
        fake_api.route("openaustralia/getRepresentatives_search_Pocock.json", part_of={"search": ["David Pocock"]})
        fake_api.route(
            "openaustralia/getSenators_search_Pocock.json", part_of={"search": ["Barbara Pocock", "David Pocock"]}
        )

        result = await call(fake_api, variant, tool, {"name": "Pocock"})

        assert not result.is_error
        assert [
            (member["name"], member["party"], member["state"]) for member in result.structured_content["members"]
        ] == [
            ("Barbara Pocock", "Australian Greens", "SA"),
            ("David Pocock", "Independent", "ACT"),
        ]

    @pytest.mark.parametrize(("variant", "tool"), LOOKUPS)
    async def test_explains_that_former_members_need_a_person_id(
        self, fake_api: FakeApi, variant: str, tool: str
    ) -> None:
        # Keith Wolahan left the House in 2025, so neither house finds him by name.
        fake_api.route("openaustralia/getRepresentatives_search_Wolahan.json", part_of={"search": ["Keith Wolahan"]})
        fake_api.route("openaustralia/getSenators_search_Wolahan.json", part_of={"search": ["Keith Wolahan"]})

        result = await call(fake_api, variant, tool, {"name": "Wolahan"})

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {tool}: OpenAustralia has no current member matching name=Wolahan. "
            "Searches find current members only. For a former member, find their person_id, for example on a "
            "search_hansard hit, and look them up by that."
        )
