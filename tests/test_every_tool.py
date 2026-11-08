"""What every tool must do with what OpenAustralia sends back.

The messages come from the shared error handling, so they're the same for every tool apart from its name.
"""

from typing import NamedTuple

import httpx2
import pytest

from openaustralia_mcp.config import Config

from .conftest import Connect, result_text
from .fake_api import FakeApi, Handler

pytestmark = pytest.mark.anyio


class Call(NamedTuple):
    tool: str
    args: dict[str, str]
    # How an error message gives the arguments.
    described: str


# One call per tool, and per kind of member lookup. Each reaches OpenAustralia, so each has to handle what comes back.
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
