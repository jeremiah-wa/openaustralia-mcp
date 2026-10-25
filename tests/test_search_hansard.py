from unittest.mock import ANY

import pytest

from .conftest import TEST_KEY, Connect, FakeApi

pytestmark = pytest.mark.anyio

HOUSING_BY_10887 = "openaustralia/getHansard_search_housing_person_10887.json"


class TestSearchRequest:
    async def test_asks_openaustralia_for_the_query_and_person(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        [request] = fake_api.requests
        assert str(request.url).startswith("https://www.openaustralia.org.au/api/getHansard?")
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "search": "housing", "person": "10887"}


class TestSearchResult:
    async def test_returns_hits_with_attribution(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        assert not result.is_error
        content = result.structured_content
        assert len(content["hits"]) == 20
        assert content["hits"][0] == {
            "gid": "2026-06-23.80.1",
            "date": "2026-06-23",
            "house": "representatives",
            "speaker": "Peter Khalil",
            "person_id": "10887",
            "debate": "Matters of Public Importance: Budget",
            "excerpt": ANY,
            "url": "https://www.openaustralia.org.au/debates/?id=2026-06-23.78.2&s=housing+speaker%3A10887#g80.1",
        }
        assert content["total_results"] == 69
        assert content["source_url"] == "https://www.openaustralia.org.au"
        assert content["licence"] == (
            "Hansard: Commonwealth of Australia, CC BY-NC-ND 3.0 AU (https://creativecommons.org/licenses/by-nc-nd/3.0/au/)"
        )


class TestExcerpt:
    async def test_strips_highlighting_and_entities(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        # The fixture has `<span class="hi">housing</span>` and `&#8212;`. OpenAustralia's `....` and `...` stay.
        assert result.structured_content["hits"][0]["excerpt"] == (
            ".... This means something to those 13 million Australian workers we've talked about. "
            "It's relieving the tax burden for so many Australians. It's giving support to 75,000 more "
            "homeowners to get into the housing market. That's support; it's not harm. And, to be fair, "
            "the shadow Treasurer talked a lot about small business—very passionately, very "
            "aggressively—and how much he loves..."
        )
