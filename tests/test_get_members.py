import pytest

from .conftest import TEST_KEY, Connect, FakeApi

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
