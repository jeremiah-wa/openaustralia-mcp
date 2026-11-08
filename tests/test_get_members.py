import httpx2
import pytest

from .conftest import TEST_KEY, Connect, result_text
from .fake_api import FIXTURES, FakeApi, Handler

pytestmark = pytest.mark.anyio

POSTCODE_3056 = "openaustralia/getRepresentatives_postcode_3056.json"


def _sharma_with(senators: httpx2.Response) -> Handler:
    """Dave Sharma's recorded records, with the list of current Senators answered as given."""

    def answer(request: httpx2.Request) -> httpx2.Response:
        function = request.url.path.rsplit("/", 1)[-1]
        if function == "getSenators":
            return senators
        return httpx2.Response(200, content=(FIXTURES / f"openaustralia/{function}_id_10942.json").read_bytes())

    return answer


class TestLookupByPostcode:
    async def test_returns_the_member_with_attribution(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(POSTCODE_3056)

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

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
            "source_url": "https://www.openaustralia.org.au",
            "licence": (
                "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
            ),
        }

    async def test_asks_openaustralia_for_that_postcode(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(POSTCODE_3056)

        async with connect() as client:
            await client.call_tool("get_members", {"postcode": "3056"})

        [request] = fake_api.requests
        assert str(request.url).startswith("https://www.openaustralia.org.au/api/getRepresentatives?")
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "postcode": "3056"}


class TestWhatClaudeSees:
    async def test_instructions_say_how_to_find_a_member(self, connect: Connect) -> None:
        async with connect() as client:
            instructions = client.instructions

        assert (
            "Start with get_members to find a member and their person_id, by postcode, name, party or state, "
            "or to look up a person_id; later calls about that member use the person_id."
        ) in (instructions or "")

    async def test_description_covers_every_argument(self, connect: Connect) -> None:
        async with connect() as client:
            tools = (await client.list_tools()).tools

        [tool] = [tool for tool in tools if tool.name == "get_members"]
        assert [
            argument for argument in tool.input_schema["properties"] if argument not in (tool.description or "")
        ] == []


class TestNoArguments:
    async def test_says_what_to_give(self, connect: Connect, fake_api: FakeApi) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: Give a postcode, a person_id, or any of name, party, state and house."
        )
        assert fake_api.requests == []


class TestLookupByPersonId:
    async def test_finds_a_former_member(self, connect: Connect, fake_api: FakeApi) -> None:
        # Keith Wolahan was the MP for Menzies until 2025, and was never a Senator.
        fake_api.route("openaustralia/getRepresentative_id_10990.json")
        fake_api.route("openaustralia/getSenator_id_10990.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10990"})

        assert not result.is_error
        assert result.structured_content["members"] == [
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
        ]

    async def test_finds_someone_who_moved_houses(self, connect: Connect, fake_api: FakeApi) -> None:
        # Dave Sharma was the MP for Wentworth until 2022, and has been a Senator for NSW since 2023.
        fake_api.route("openaustralia/getRepresentative_id_10942.json")
        fake_api.route("openaustralia/getSenator_id_10942.json")
        fake_api.route("openaustralia/getSenators.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10942"})

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
                "positions": [
                    "Shadow Assistant Minister for Citizenship and Multicultural Affairs",
                    "Shadow Assistant Minister for International Development and the Indo-Pacific",
                ],
                "url": "https://www.openaustralia.org.au/senator/?p=10942",
            },
        ]

    async def test_keeps_the_former_record_of_a_senator_who_came_back(
        self, connect: Connect, fake_api: FakeApi
    ) -> None:
        # Don Farrell left the Senate in 2014 and came back in 2016.
        fake_api.route("openaustralia/getRepresentative_id_10708.json")
        fake_api.route("openaustralia/getSenator_id_10708.json")
        fake_api.route("openaustralia/getSenators.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10708"})

        assert not result.is_error
        [current, former] = result.structured_content["members"]
        assert (current["current"], current["left"]) == (True, None)
        assert current["positions"] == [
            "Minister for Trade and Tourism",
            "Deputy Leader of the Government in the Senate",
            "Special Minister of State",
        ]
        assert (former["current"], former["left"]) == (False, "2014-06-30")
        assert former["positions"] == []

    async def test_needs_no_list_of_senators_for_a_former_senator(self, connect: Connect, fake_api: FakeApi) -> None:
        # Kristina Keneally left the Senate in 2022.
        fake_api.route("openaustralia/getRepresentative_id_10906.json")
        fake_api.route("openaustralia/getSenator_id_10906.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10906"})

        assert not result.is_error
        assert [member["left"] for member in result.structured_content["members"]] == ["2022-04-13"]
        assert len(fake_api.requests) == 2

    async def test_keeps_a_current_senator_the_list_leaves_out(self, connect: Connect, fake_api: FakeApi) -> None:
        # Not seen in a real response. If the two functions disagree, the person still has their record.
        fake_api.serve(_sharma_with(httpx2.Response(200, json={})))

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10942"})

        assert not result.is_error
        [_, senator] = result.structured_content["members"]
        assert (senator["state"], senator["current"], senator["positions"]) == ("NSW", True, [])

    async def test_fails_when_only_the_list_of_senators_fails(self, connect: Connect, fake_api: FakeApi) -> None:
        # Empty positions would say the Senator holds no office, so the lookup fails rather than guess.
        fake_api.serve(_sharma_with(httpx2.Response(502)))

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10942"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia didn't respond normally (HTTP 502). Try again later."
        )

    async def test_asks_both_houses(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentative_id_10990.json")
        fake_api.route("openaustralia/getSenator_id_10990.json")

        async with connect() as client:
            await client.call_tool("get_members", {"person_id": "10990"})

        asked = {(request.url.path.rsplit("/", 1)[-1], request.url.params["id"]) for request in fake_api.requests}
        assert asked == {("getRepresentative", "10990"), ("getSenator", "10990")}

    async def test_says_when_neither_house_knows_the_person(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentative_id_99999.json")
        fake_api.route("openaustralia/getSenator_id_99999.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "99999"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia has no member of either house with person_id 99999."
        )


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
    async def test_lists_the_states_senators(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getSenators_state_Tasmania.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"state": "TAS"})

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

    @pytest.mark.parametrize(
        ("state", "spelling"),
        [
            ("NSW", "NSW"),
            ("VIC", "Victoria"),
            ("QLD", "Queensland"),
            ("WA", "WA"),
            ("SA", "SA"),
            ("TAS", "Tasmania"),
            ("ACT", "ACT"),
            ("NT", "NT"),
        ],
    )
    async def test_sends_a_spelling_openaustralia_accepts(
        self, connect: Connect, fake_api: FakeApi, state: str, spelling: str
    ) -> None:
        # From live calls: QLD gets no one where Queensland works, and New South Wales no one where NSW works.
        fake_api.serve(lambda request: httpx2.Response(200, json=[]))

        async with connect() as client:
            await client.call_tool("get_members", {"state": state})

        [request] = fake_api.requests
        assert request.url.params["state"] == spelling


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


class TestLookupByParty:
    async def test_finds_the_partys_members_in_both_houses(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_party_Greens.json", part_of={"party": ["Australian Greens"]})
        fake_api.route("openaustralia/getSenators_party_Greens.json", part_of={"party": ["Australian Greens"]})

        async with connect() as client:
            result = await client.call_tool("get_members", {"party": "Greens"})

        assert not result.is_error
        members = result.structured_content["members"]
        assert [(member["name"], member["house"]) for member in members] == [
            ("Elizabeth Watson-Brown", "representatives"),
            *((name, "senate") for name in GREENS_SENATORS),
        ]
        assert members[0]["electorate"] == "Ryan"

    async def test_house_limits_it_to_the_senate(self, connect: Connect, fake_api: FakeApi) -> None:
        # Only the Senate is recorded, so asking the House as well would fail.
        fake_api.route("openaustralia/getSenators_party_Greens.json", part_of={"party": ["Australian Greens"]})

        async with connect() as client:
            result = await client.call_tool("get_members", {"party": "Greens", "house": "senate"})

        assert not result.is_error
        assert [member["name"] for member in result.structured_content["members"]] == GREENS_SENATORS

    async def test_house_limits_it_to_the_house_of_representatives(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_party_Greens.json", part_of={"party": ["Australian Greens"]})

        async with connect() as client:
            result = await client.call_tool("get_members", {"party": "Greens", "house": "representatives"})

        assert not result.is_error
        assert [member["name"] for member in result.structured_content["members"]] == ["Elizabeth Watson-Brown"]

    async def test_an_api_error_names_the_house_too(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getRepresentatives_postcode_0000.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"party": "Greens", "house": "senate"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia returned an error for party=Greens, house=senate: "
            "Unknown postcode"
        )


class TestLookupByName:
    async def test_finds_senators_when_no_mp_matches(self, connect: Connect, fake_api: FakeApi) -> None:
        # No MP is called Pocock, so getRepresentatives sends `{}`. Two Senators are.
        fake_api.route("openaustralia/getRepresentatives_search_Pocock.json", part_of={"search": ["David Pocock"]})
        fake_api.route(
            "openaustralia/getSenators_search_Pocock.json", part_of={"search": ["Barbara Pocock", "David Pocock"]}
        )

        async with connect() as client:
            result = await client.call_tool("get_members", {"name": "Pocock"})

        assert not result.is_error
        assert [
            (member["name"], member["party"], member["state"]) for member in result.structured_content["members"]
        ] == [
            ("Barbara Pocock", "Australian Greens", "SA"),
            ("David Pocock", "Independent", "ACT"),
        ]

    async def test_finds_an_mp_when_no_senator_matches(self, connect: Connect, fake_api: FakeApi) -> None:
        # No Senator is called Khalil, so getSenators sends `{}`.
        fake_api.route("openaustralia/getRepresentatives_search_Khalil.json", part_of={"search": ["Peter Khalil"]})
        fake_api.route("openaustralia/getSenators_search_Khalil.json", part_of={"search": ["Peter Khalil"]})

        async with connect() as client:
            result = await client.call_tool("get_members", {"name": "Khalil"})

        assert not result.is_error
        assert [
            (member["name"], member["electorate"], member["house"]) for member in result.structured_content["members"]
        ] == [("Peter Khalil", "Wills", "representatives")]

    async def test_explains_that_former_members_need_a_person_id(self, connect: Connect, fake_api: FakeApi) -> None:
        # Keith Wolahan left the House in 2025, so neither house finds him by name.
        fake_api.route("openaustralia/getRepresentatives_search_Wolahan.json", part_of={"search": ["Keith Wolahan"]})
        fake_api.route("openaustralia/getSenators_search_Wolahan.json", part_of={"search": ["Keith Wolahan"]})

        async with connect() as client:
            result = await client.call_tool("get_members", {"name": "Wolahan"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia has no current member matching name=Wolahan. "
            "Searches find current members only. For a former member, find their person_id, for example on a "
            "search_hansard hit, and look them up by that."
        )


class TestArgumentsThatDontGoTogether:
    @pytest.mark.parametrize(
        "other",
        [{"postcode": "3056"}, {"name": "Sharma"}, {"party": "Liberal"}, {"state": "NSW"}, {"house": "senate"}],
    )
    async def test_person_id_with_anything_else(
        self, connect: Connect, fake_api: FakeApi, other: dict[str, str]
    ) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {"person_id": "10942", **other})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A person_id finds one person in both houses by itself. "
            "Give it on its own."
        )
        assert fake_api.requests == []

    @pytest.mark.parametrize("other", [{"name": "Khalil"}, {"party": "Labor"}, {"state": "VIC"}, {"house": "senate"}])
    async def test_postcode_with_a_search(self, connect: Connect, fake_api: FakeApi, other: dict[str, str]) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056", **other})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A postcode finds the MPs for that area by itself. Give it on its own, "
            "or search by name, party, state and house instead."
        )
        assert fake_api.requests == []

    async def test_postcode_with_its_own_house(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(POSTCODE_3056)

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056", "house": "representatives"})

        assert not result.is_error

    async def test_state_with_the_house_of_representatives(self, connect: Connect, fake_api: FakeApi) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {"state": "TAS", "house": "representatives"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: A state means Senators: they represent a whole state or territory. "
            "MPs represent electorates, so for MPs give a postcode or a name instead."
        )
        assert fake_api.requests == []


class TestPostcodeValidation:
    @pytest.mark.parametrize("postcode", ["30", "30560", "abcd", " 3056"])
    async def test_rejects_a_malformed_postcode_without_a_request(
        self, connect: Connect, fake_api: FakeApi, postcode: str
    ) -> None:
        fake_api.route(POSTCODE_3056)

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": postcode})

        assert result.is_error
        assert "postcode" in result_text(result)
        assert fake_api.requests == []


class TestPostcodeWithoutCurrentMember:
    """OpenAustralia still maps some postcodes to abolished electorates (e.g. Higgins) and puts `false` in their place."""

    async def test_lists_the_members_it_can_match_and_warns_the_list_may_be_incomplete(
        self, connect: Connect, fake_api: FakeApi
    ) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3181.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3181"})

        assert not result.is_error
        assert result.structured_content["members"] == [
            {
                "person_id": "10934",
                "name": "Josh Burns",
                "party": "Australian Labor Party",
                "house": "representatives",
                "electorate": "Macnamara",
                "state": None,
                "current": True,
                "left": None,
                "positions": [],
                "url": "https://www.openaustralia.org.au/mp/?p=10934",
            }
        ]
        assert result.structured_content["note"] == (
            "OpenAustralia couldn't match part of this postcode to a current member, so this list may be "
            "incomplete. Its postcode data can lag behind changes to electorate boundaries."
        )

    async def test_explains_when_no_current_member_is_on_record(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3142.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3142"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia has no current member on record for postcode 3142. "
            "Its postcode data can lag behind changes to electorate boundaries, so try a neighbouring postcode."
        )
