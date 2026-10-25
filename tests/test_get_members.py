import pytest

from openaustralia_mcp.config import Config

from .conftest import TEST_KEY, Connect, FakeApi, result_text

pytestmark = pytest.mark.anyio

POSTCODE_3056 = "openaustralia/getRepresentatives_postcode_3056.json"


class TestLookupByPostcode:
    async def test_returns_the_member_with_attribution(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(POSTCODE_3056)

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert not result.is_error
        assert result.structured_content == {
            "members": [
                {
                    "person_id": "10887",
                    "name": "Peter Khalil",
                    "party": "Australian Labor Party",
                    "electorate": "Wills",
                    "house": "representatives",
                    "positions": ["Assistant Minister for Defence"],
                    "url": "https://www.openaustralia.org.au/mp/?p=10887",
                }
            ],
            "source_url": "https://www.openaustralia.org.au",
            "licence": (
                "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
            ),
        }

    async def test_asks_openaustralia_for_that_postcode(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(POSTCODE_3056)

        async with connect() as client:
            await client.call_tool("get_members", {"postcode": "3056"})

        [request] = fake_api.requests
        assert str(request.url).startswith("https://www.openaustralia.org.au/api/getRepresentatives?")
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "postcode": "3056"}


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
        fake_api.serve_fixture(POSTCODE_3056)

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
