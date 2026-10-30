import logging

import httpx2
import pytest

from openaustralia_mcp.config import Config

from .conftest import TEST_KEY, Connect, result_text
from .fake_api import FakeApi, Handler

pytestmark = pytest.mark.anyio

POSTCODE_3056 = "openaustralia/getRepresentatives_postcode_3056.json"


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


class TestNoArguments:
    async def test_says_what_to_give(self, connect: Connect, fake_api: FakeApi) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {})

        assert result.is_error
        assert result_text(result) == "Error executing tool get_members: Give a postcode or a person_id."
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
                "positions": [],
                "url": "https://www.openaustralia.org.au/senator/?p=10942",
            },
        ]

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


class TestMissingKey:
    async def test_explains_where_to_get_a_key(self, connect: Connect) -> None:
        async with connect(Config()) as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: No OpenAustralia key set. "
            "Get one at https://www.openaustralia.org.au/api/key, "
            "then set OPENAUSTRALIA_API_KEY in your MCP client config."
        )

    async def test_makes_no_request(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(POSTCODE_3056)

        async with connect(Config()) as client:
            await client.call_tool("get_members", {"postcode": "3056"})

        assert fake_api.requests == []


class TestRejectedKey:
    async def test_says_the_key_was_rejected(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getRepresentatives_bad_key.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: The OpenAustralia key was rejected. "
            "Check it or get a new one at https://www.openaustralia.org.au/api/key."
        )


class TestApiError:
    async def test_passes_on_the_api_error_with_the_arguments(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_0000.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "0000"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool get_members: OpenAustralia returned an error for postcode=0000: Unknown postcode"
        )


def _connection_refused(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection refused", request=request)


class TestApiUnavailable:
    @pytest.mark.parametrize(
        ("handler", "message"),
        [
            (_connection_refused, "OpenAustralia couldn't be reached. Try again later."),
            (
                lambda request: httpx2.Response(502, text="Bad gateway"),
                "OpenAustralia didn't respond normally (HTTP 502). Try again later.",
            ),
            (
                lambda request: httpx2.Response(200, text="<html>Just a moment...</html>"),
                "OpenAustralia didn't respond normally (HTTP 200). Try again later.",
            ),
        ],
        ids=["connection-error", "server-error", "not-json"],
    )
    async def test_says_to_try_again_later(
        self, connect: Connect, fake_api: FakeApi, handler: Handler, message: str
    ) -> None:
        fake_api.serve(handler)

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert result.is_error
        assert result_text(result) == f"Error executing tool get_members: {message}"


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


def _connection_refused_naming_the_url(request: httpx2.Request) -> httpx2.Response:
    # Real HTTP errors mention the URL, and the URL contains the key.
    raise httpx2.ConnectError(f"connection refused: {request.url}", request=request)


LEAK_CASES = {
    "success": "openaustralia/getRepresentatives_postcode_3056.json",
    "rejected-key": "openaustralia/getRepresentatives_bad_key.json",
    "api-error": "openaustralia/getRepresentatives_postcode_0000.json",
    "connection-error": _connection_refused_naming_the_url,
    "server-error": lambda request: httpx2.Response(500),
}


class TestKeyNeverLeaks:
    @pytest.fixture(params=LEAK_CASES.values(), ids=LEAK_CASES.keys())
    def api_behaviour(self, request: pytest.FixtureRequest, fake_api: FakeApi) -> None:
        if isinstance(request.param, str):
            fake_api.serve_fixture(request.param)
        else:
            fake_api.serve(request.param)

    async def test_not_in_the_result(self, connect: Connect, api_behaviour: None) -> None:
        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert TEST_KEY not in result_text(result)

    async def test_not_in_the_logs(
        self, connect: Connect, api_behaviour: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)

        async with connect() as client:
            await client.call_tool("get_members", {"postcode": "3056"})

        assert caplog.records, "expected some log output to check"
        assert TEST_KEY not in caplog.text


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
