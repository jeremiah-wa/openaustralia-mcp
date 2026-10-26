"""The member-lookup variants for #8, through the tool call, as Claude uses them (see docs/evals.md#variants).

Each test runs the same lookup on both variants and expects the same result: the variants may differ only in what
Claude sees, never in what it gets back.
"""

import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult, Tool

from evals.variants import VARIANTS
from openaustralia_mcp.config import Config

from .conftest import TEST_CONFIG, TEST_KEY, result_text
from .fake_api import FakeApi

pytestmark = pytest.mark.anyio

SOURCE_URL = "https://www.openaustralia.org.au"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
)


@asynccontextmanager
async def connect(variant: str, fake_api: FakeApi, config: Config = TEST_CONFIG) -> AsyncGenerator[Client, None]:
    async with (
        httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
        Client(VARIANTS[variant](http, config)) as client,
    ):
        yield client


async def call(
    fake_api: FakeApi, variant: str, tool: str, args: dict[str, Any], config: Config = TEST_CONFIG
) -> CallToolResult:
    async with connect(variant, fake_api, config) as client:
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


class TestArgumentsThatDontGoTogether:
    """The parameters variant's one tool takes any mix of arguments, so it explains the mixes that make no sense."""

    async def test_none_at_all(self, fake_api: FakeApi) -> None:
        result = await call(fake_api, "parameters", "get_members", {})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: Give a postcode, a person_id, or any of name, party, state and house."
        )
        assert fake_api.requests == []

    @pytest.mark.parametrize(
        "other",
        [{"postcode": "3056"}, {"name": "Sharma"}, {"party": "Liberal"}, {"state": "NSW"}, {"house": "senate"}],
    )
    async def test_person_id_with_anything_else(self, fake_api: FakeApi, other: dict[str, str]) -> None:
        result = await call(fake_api, "parameters", "get_members", {"person_id": "10942", **other})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A person_id finds one person in both houses by itself. "
            "Give it on its own."
        )
        assert fake_api.requests == []

    @pytest.mark.parametrize("other", [{"name": "Khalil"}, {"party": "Labor"}, {"state": "VIC"}, {"house": "senate"}])
    async def test_postcode_with_a_search(self, fake_api: FakeApi, other: dict[str, str]) -> None:
        result = await call(fake_api, "parameters", "get_members", {"postcode": "3056", **other})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A postcode finds the MPs for that area by itself. Give it on its own, "
            "or search by name, party, state and house instead."
        )
        assert fake_api.requests == []

    async def test_postcode_with_its_own_house(self, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")

        result = await call(fake_api, "parameters", "get_members", {"postcode": "3056", "house": "representatives"})

        assert not result.is_error

    async def test_state_with_the_house_of_representatives(self, fake_api: FakeApi) -> None:
        result = await call(fake_api, "parameters", "get_members", {"state": "TAS", "house": "representatives"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A state means Senators: they represent a whole state or territory. "
            "MPs represent electorates, so for MPs give a postcode or a name instead."
        )
        assert fake_api.requests == []


class TestSearchMembersNeedsAFilter:
    async def test_with_neither_name_nor_party(self, fake_api: FakeApi) -> None:
        # Otherwise it would list every current member of both houses.
        result = await call(fake_api, "tools", "search_members", {})

        assert result.is_error
        assert result_text(result) == "Error executing tool search_members: Give a name, a party, or both."
        assert fake_api.requests == []


async def what_claude_sees(variant: str, fake_api: FakeApi) -> tuple[str, dict[str, Tool]]:
    async with connect(variant, fake_api) as client:
        return client.instructions or "", {tool.name: tool for tool in (await client.list_tools()).tools}


def texts(instructions: str, tools: dict[str, Tool]) -> list[str]:
    """Everything written for Claude: the instructions, and each tool's and argument's description."""
    arguments = [
        argument.get("description", "")
        for tool in tools.values()
        for argument in tool.input_schema.get("properties", {}).values()
    ]
    return [instructions, *(tool.description or "" for tool in tools.values()), *arguments]


# What each variant's instructions say in place of the server's line about finding members.
PARAMETERS_MEMBERS_LINE = (
    "Start with get_members to find a member and their person_id, by postcode, name, party or state, "
    "or to look up a person_id; later calls about that member use the person_id."
)
TOOLS_MEMBERS_LINE = (
    "Start with get_members (by postcode), search_members (by name or party) or get_senators (by state) "
    "to find a member and their person_id, and get_member to look up a person_id; later calls about that "
    "member use the person_id."
)
MEMBER_TOOLS = {"parameters": {"get_members"}, "tools": {"get_members", "get_member", "get_senators", "search_members"}}


class TestWhatClaudeSees:
    """The variants differ only in their member tools, and in the text that names them."""

    @pytest.mark.parametrize("variant", ["parameters", "tools"])
    async def test_only_the_member_tools_change(self, fake_api: FakeApi, variant: str) -> None:
        _, current = await what_claude_sees("current", fake_api)
        _, tools = await what_claude_sees(variant, fake_api)

        assert set(tools) - MEMBER_TOOLS[variant] == set(current) - {"get_members"}

    @pytest.mark.parametrize(
        ("variant", "line"),
        [("parameters", PARAMETERS_MEMBERS_LINE), ("tools", TOOLS_MEMBERS_LINE)],
    )
    async def test_instructions_change_only_in_the_members_line(
        self, fake_api: FakeApi, variant: str, line: str
    ) -> None:
        current, _ = await what_claude_sees("current", fake_api)
        instructions, _ = await what_claude_sees(variant, fake_api)

        members_line = next(text for text in current.splitlines() if text.startswith("Start with get_members"))
        assert instructions.splitlines() == [line if text == members_line else text for text in current.splitlines()]

    @pytest.mark.parametrize(
        ("variant", "description"),
        [
            ("current", "Only speeches by this member. Get it from get_members."),
            ("parameters", "Only speeches by this member. Get it from get_members."),
            ("tools", "Only speeches by this member. Get it from get_members, search_members or get_senators."),
        ],
    )
    async def test_search_hansard_says_where_a_person_id_comes_from(
        self, fake_api: FakeApi, variant: str, description: str
    ) -> None:
        # Building the variants first checks that rewording one doesn't change the server's own tools.
        for other in VARIANTS:
            await what_claude_sees(other, fake_api)
        _, tools = await what_claude_sees(variant, fake_api)

        assert tools["search_hansard"].input_schema["properties"]["person_id"]["description"] == description

    @pytest.mark.parametrize("variant", ["parameters", "tools"])
    async def test_names_no_tool_the_variant_lacks(self, fake_api: FakeApi, variant: str) -> None:
        instructions, tools = await what_claude_sees(variant, fake_api)
        every_tool = set().union(*MEMBER_TOOLS.values(), tools)

        named = {name for text in texts(instructions, tools) for name in every_tool if re.search(rf"\b{name}\b", text)}

        assert named <= set(tools)

    async def test_shared_arguments_are_described_alike(self, fake_api: FakeApi) -> None:
        descriptions: dict[str, set[str]] = {}
        for variant, names in MEMBER_TOOLS.items():
            _, tools = await what_claude_sees(variant, fake_api)
            for name in names:
                for argument, schema in tools[name].input_schema["properties"].items():
                    descriptions.setdefault(argument, set()).add(schema["description"])

        assert {argument for argument, seen in descriptions.items() if len(seen) > 1} == set()


# Every member tool in both variants, with arguments that reach OpenAustralia.
EVERY_LOOKUP = [
    ("parameters", "get_members", {"postcode": "3056"}),
    ("parameters", "get_members", {"person_id": "10942"}),
    ("parameters", "get_members", {"name": "Pocock"}),
    ("tools", "get_members", {"postcode": "3056"}),
    ("tools", "get_member", {"person_id": "10942"}),
    ("tools", "get_senators", {"state": "TAS"}),
    ("tools", "search_members", {"name": "Pocock"}),
]
EVERY_LOOKUP_IDS = [f"{variant}-{tool}-{next(iter(args))}" for variant, tool, args in EVERY_LOOKUP]


def _connection_refused_naming_the_url(request: httpx2.Request) -> httpx2.Response:
    # Real HTTP errors mention the URL, and the URL contains the key.
    raise httpx2.ConnectError(f"connection refused: {request.url}", request=request)


LEAK_CASES = {
    "rejected-key": "openaustralia/getRepresentatives_bad_key.json",
    "api-error": "openaustralia/getRepresentatives_postcode_0000.json",
    "connection-error": _connection_refused_naming_the_url,
    "server-error": lambda request: httpx2.Response(500),
}


class TestApiProblems:
    """Every lookup goes through the client's own key and error handling, so these guard it rather than drive it."""

    @pytest.mark.parametrize(("variant", "tool", "args"), EVERY_LOOKUP, ids=EVERY_LOOKUP_IDS)
    async def test_explains_a_missing_key(
        self, fake_api: FakeApi, variant: str, tool: str, args: dict[str, str]
    ) -> None:
        result = await call(fake_api, variant, tool, args, Config())

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {tool}: No OpenAustralia key set. Get one at https://www.openaustralia.org.au/api/key, "
            "then set OPENAUSTRALIA_API_KEY in your MCP client config."
        )
        assert fake_api.requests == []

    @pytest.mark.parametrize(("variant", "tool", "args"), EVERY_LOOKUP, ids=EVERY_LOOKUP_IDS)
    async def test_says_the_key_was_rejected(
        self, fake_api: FakeApi, variant: str, tool: str, args: dict[str, str]
    ) -> None:
        fake_api.serve_fixture("openaustralia/getRepresentatives_bad_key.json")

        result = await call(fake_api, variant, tool, args)

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {tool}: The OpenAustralia key was rejected. "
            "Check it or get a new one at https://www.openaustralia.org.au/api/key."
        )

    @pytest.mark.parametrize(("variant", "tool"), [("parameters", "get_members"), ("tools", "get_members")])
    async def test_passes_on_an_api_error(self, fake_api: FakeApi, variant: str, tool: str) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_0000.json")

        result = await call(fake_api, variant, tool, {"postcode": "0000"})

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {tool}: OpenAustralia returned an error for postcode=0000: Unknown postcode"
        )


class TestKeyNeverLeaks:
    @pytest.fixture(params=LEAK_CASES.values(), ids=LEAK_CASES.keys())
    def api_behaviour(self, request: pytest.FixtureRequest, fake_api: FakeApi) -> None:
        if isinstance(request.param, str):
            fake_api.serve_fixture(request.param)
        else:
            fake_api.serve(request.param)

    @pytest.mark.parametrize(("variant", "tool", "args"), EVERY_LOOKUP, ids=EVERY_LOOKUP_IDS)
    async def test_not_in_the_result_or_the_logs(
        self,
        fake_api: FakeApi,
        api_behaviour: None,
        caplog: pytest.LogCaptureFixture,
        variant: str,
        tool: str,
        args: dict[str, str],
    ) -> None:
        caplog.set_level(logging.DEBUG)

        result = await call(fake_api, variant, tool, args)

        assert result.is_error
        assert TEST_KEY not in result_text(result)
        assert caplog.records, "expected some log output to check"
        assert TEST_KEY not in caplog.text
