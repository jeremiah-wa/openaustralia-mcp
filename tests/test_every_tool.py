"""What every tool must do with what OpenAustralia sends back.

The messages come from the shared error handling, so they're the same for every tool apart from its name.
"""

from typing import NamedTuple

import pytest

from openaustralia_mcp.config import Config

from .conftest import Connect, result_text
from .fake_api import FakeApi

pytestmark = pytest.mark.anyio


class Call(NamedTuple):
    tool: str
    args: dict[str, str]


# One call per tool, and per kind of member lookup. Each reaches OpenAustralia, so each has to handle what comes back.
EVERY_CALL = [
    Call("get_members", {"postcode": "3056"}),
    Call("get_members", {"person_id": "10942"}),
    Call("get_members", {"name": "Pocock"}),
    Call("get_members", {"party": "Greens"}),
    Call("get_members", {"state": "TAS"}),
    Call("search_hansard", {"query": "housing", "person_id": "10887"}),
    Call("read_debate", {"gid": "2026-06-23.80.1", "house": "representatives"}),
]
EVERY_CALL_IDS = ["-".join([call.tool, *call.args]) for call in EVERY_CALL]

# OpenAustralia rejects a bad key the same way, whichever function is called.
BAD_KEY = "openaustralia/getRepresentatives_bad_key.json"


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
