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
