"""What every tool must do with what OpenAustralia sends back.

The messages come from the shared error handling, so they're the same for every tool apart from its name.
"""

import logging
from typing import NamedTuple

import httpx2
import pytest

from openaustralia_mcp.config import Config

from .conftest import TEST_KEY, Connect, result_text
from .fake_api import FakeApi, Handler

pytestmark = pytest.mark.anyio


class Call(NamedTuple):
    tool: str
    args: dict[str, str]
    # How an error message gives the arguments.
    described: str


# One call per tool, and per kind of member lookup. Each reaches OpenAustralia, so each has to handle what comes back.
# A new tool gets a row here, not its own copies of these tests.
EVERY_CALL = [
    Call("get_members", {"postcode": "3056"}, "postcode=3056"),
    Call("get_members", {"person_id": "10942"}, "person_id=10942"),
    Call("get_members", {"name": "Pocock"}, "name=Pocock"),
    Call("get_members", {"party": "Greens"}, "party=Greens"),
    Call("get_members", {"state": "TAS"}, "state=TAS"),
    Call("search_hansard", {"query": "housing", "person_id": "10887"}, "query=housing, person_id=10887"),
    Call(
        "read_debate",
        {"gid": "2026-06-23.80.1", "house": "representatives"},
        "gid=2026-06-23.80.1, house=representatives",
    ),
]
EVERY_CALL_IDS = ["-".join([call.tool, *call.args]) for call in EVERY_CALL]

# The recorded responses that answer every call in EVERY_CALL.
EVERY_ANSWER = [
    "openaustralia/getRepresentatives_postcode_3056.json",
    "openaustralia/getRepresentative_id_10942.json",
    "openaustralia/getSenator_id_10942.json",
    "openaustralia/getSenators.json",
    "openaustralia/getRepresentatives_search_Pocock.json",
    "openaustralia/getSenators_search_Pocock.json",
    "openaustralia/getRepresentatives_party_Greens.json",
    "openaustralia/getSenators_party_Greens.json",
    "openaustralia/getSenators_state_Tasmania.json",
    "openaustralia/getHansard_search_housing_person_10887.json",
    "openaustralia/getDebates_representatives_2026-06-23.80.1.json",
]

# OpenAustralia rejects a bad key the same way, whichever function is called.
BAD_KEY = "openaustralia/getRepresentatives_bad_key.json"
# Any error will do for every call: the tools pass the message on as it is.
API_ERROR = "openaustralia/getRepresentatives_postcode_0000.json"


class TestMissingKey:
    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_explains_where_to_get_a_key(self, connect: Connect, call: Call) -> None:
        async with connect(Config()) as client:
            result = await client.call_tool(call.tool, call.args)

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {call.tool}: No OpenAustralia key set. "
            "Get one at https://www.openaustralia.org.au/api/key, "
            "then set OPENAUSTRALIA_API_KEY in your MCP client config."
        )

    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_makes_no_request(self, connect: Connect, fake_api: FakeApi, call: Call) -> None:
        async with connect(Config()) as client:
            await client.call_tool(call.tool, call.args)

        assert fake_api.requests == []


class TestRejectedKey:
    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_says_the_key_was_rejected(self, connect: Connect, fake_api: FakeApi, call: Call) -> None:
        fake_api.serve_fixture(BAD_KEY)

        async with connect() as client:
            result = await client.call_tool(call.tool, call.args)

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {call.tool}: The OpenAustralia key was rejected. "
            "Check it or get a new one at https://www.openaustralia.org.au/api/key."
        )


class TestApiError:
    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_passes_on_the_api_error_with_the_arguments(
        self, connect: Connect, fake_api: FakeApi, call: Call
    ) -> None:
        fake_api.serve_fixture(API_ERROR)

        async with connect() as client:
            result = await client.call_tool(call.tool, call.args)

        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool {call.tool}: OpenAustralia returned an error for {call.described}: Unknown postcode"
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
    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_says_to_try_again_later(
        self, connect: Connect, fake_api: FakeApi, call: Call, handler: Handler, message: str
    ) -> None:
        fake_api.serve(handler)

        async with connect() as client:
            result = await client.call_tool(call.tool, call.args)

        assert result.is_error
        assert result_text(result) == f"Error executing tool {call.tool}: {message}"


def _connection_refused_naming_the_url(request: httpx2.Request) -> httpx2.Response:
    # Real HTTP errors mention the URL, and the URL contains the key.
    raise httpx2.ConnectError(f"connection refused: {request.url}", request=request)


# The recorded responses that answer every call, a recorded response that answers any call, or a handler.
LEAK_CASES: dict[str, list[str] | str | Handler] = {
    "success": EVERY_ANSWER,
    "rejected-key": BAD_KEY,
    "api-error": API_ERROR,
    # What OpenAustralia sends for a gid it doesn't have, with the URL in it.
    "not-found": lambda request: httpx2.Response(404, text=f"<html>{request.url}</html>"),
    "connection-error": _connection_refused_naming_the_url,
    "server-error": lambda request: httpx2.Response(500),
}


class TestKeyNeverLeaks:
    @pytest.fixture(params=LEAK_CASES.values(), ids=LEAK_CASES.keys())
    def api_behaviour(self, request: pytest.FixtureRequest, fake_api: FakeApi) -> None:
        if isinstance(request.param, list):
            for name in request.param:
                fake_api.route(name)
        elif isinstance(request.param, str):
            fake_api.serve_fixture(request.param)
        else:
            fake_api.serve(request.param)

    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_not_in_the_result(self, connect: Connect, api_behaviour: None, call: Call) -> None:
        async with connect() as client:
            result = await client.call_tool(call.tool, call.args)

        assert TEST_KEY not in result_text(result)

    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_not_in_the_logs(
        self, connect: Connect, api_behaviour: None, caplog: pytest.LogCaptureFixture, call: Call
    ) -> None:
        caplog.set_level(logging.DEBUG)

        async with connect() as client:
            await client.call_tool(call.tool, call.args)

        assert caplog.records, "expected some log output to check"
        assert TEST_KEY not in caplog.text


class TestEveryCall:
    async def test_covers_every_tool_the_server_lists(self, connect: Connect) -> None:
        async with connect() as client:
            tools = (await client.list_tools()).tools

        assert {tool.name for tool in tools} == {call.tool for call in EVERY_CALL}

    @pytest.mark.parametrize("call", EVERY_CALL, ids=EVERY_CALL_IDS)
    async def test_succeeds_with_the_recorded_answers(self, connect: Connect, fake_api: FakeApi, call: Call) -> None:
        # So the success case in TestKeyNeverLeaks checks a result, not an error.
        for name in EVERY_ANSWER:
            fake_api.route(name)

        async with connect() as client:
            result = await client.call_tool(call.tool, call.args)

        assert not result.is_error, result_text(result)
