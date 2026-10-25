from unittest.mock import ANY

import httpx2
import pytest

from openaustralia_mcp.config import Config

from .conftest import TEST_KEY, Connect, FakeApi, Handler, result_text

pytestmark = pytest.mark.anyio

HOUSING_BY_10887 = "openaustralia/getHansard_search_housing_person_10887.json"
NDIS = "openaustralia/getHansard_search_ndis.json"


class TestSearchRequest:
    async def test_asks_openaustralia_for_the_query_and_person(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        [request] = fake_api.requests
        assert str(request.url).startswith("https://www.openaustralia.org.au/api/getHansard?")
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "search": "housing", "person": "10887"}

    async def test_sends_no_person_for_a_query_alone(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(NDIS)

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "NDIS"})

        assert not result.is_error
        [request] = fake_api.requests
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "search": "NDIS"}

    async def test_searches_by_person_alone(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getHansard_person_10887.json")

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"person_id": "10887"})

        assert not result.is_error
        assert result.structured_content["total_results"] == 545
        [request] = fake_api.requests
        assert dict(request.url.params) == {"key": TEST_KEY, "output": "js", "person": "10887"}


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

    async def test_labels_senate_and_house_hits(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(NDIS)

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "NDIS"})

        hits = {hit["gid"]: hit for hit in result.structured_content["hits"]}
        assert hits["2026-10-15.118.1"]["house"] == "senate"
        assert hits["2026-10-15.118.1"]["url"] == (
            "https://www.openaustralia.org.au/senate/?id=2026-10-15.117.1&s=NDIS#g118.1"
        )
        assert hits["2026-10-15.11.1"]["house"] == "representatives"
        assert (
            hits["2026-10-15.11.1"]["url"] == "https://www.openaustralia.org.au/debates/?id=2026-10-15.8.2&s=NDIS#g11.1"
        )

    async def test_returns_no_hits_without_error(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getHansard_search_no_results.json")

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "xyzzyplughnonsenseword"})

        assert not result.is_error
        assert result.structured_content["hits"] == []
        assert result.structured_content["total_results"] == 0


class TestArguments:
    async def test_needs_a_query_or_person_id(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            result = await client.call_tool("search_hansard", {})

        assert result.is_error
        assert result_text(result) == "Error executing tool search_hansard: Give a query, a person_id, or both."
        assert fake_api.requests == []

    @pytest.mark.parametrize(
        ("arguments", "name"),
        [
            ({"person_id": "abc"}, "person_id"),
            ({"person_id": " 10887"}, "person_id"),
            ({"person_id": ""}, "person_id"),
            ({"query": ""}, "query"),
        ],
    )
    async def test_rejects_malformed_arguments_without_a_request(
        self, connect: Connect, fake_api: FakeApi, arguments: dict[str, str], name: str
    ) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect() as client:
            result = await client.call_tool("search_hansard", arguments)

        assert result.is_error
        assert name in result_text(result)
        assert fake_api.requests == []


class TestMissingKey:
    async def test_explains_where_to_get_a_key(self, connect: Connect) -> None:
        async with connect(Config()) as client:
            result = await client.call_tool("search_hansard", {"query": "housing"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool search_hansard: No OpenAustralia key set. "
            "Get one at https://www.openaustralia.org.au/api/key, "
            "then set OPENAUSTRALIA_API_KEY in your MCP client config."
        )

    async def test_makes_no_request(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(HOUSING_BY_10887)

        async with connect(Config()) as client:
            await client.call_tool("search_hansard", {"query": "housing"})

        assert fake_api.requests == []


class TestRejectedKey:
    async def test_says_the_key_was_rejected(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getHansard_bad_key.json")

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "housing"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool search_hansard: The OpenAustralia key was rejected. "
            "Check it or get a new one at https://www.openaustralia.org.au/api/key."
        )


class TestApiError:
    async def test_passes_on_the_api_error_with_the_arguments(self, connect: Connect, fake_api: FakeApi) -> None:
        # Recorded from a call with no parameters, which the tool itself never makes.
        fake_api.serve_fixture("openaustralia/getHansard_no_parameters.json")

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "housing", "person_id": "10887"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool search_hansard: OpenAustralia returned an error for query=housing, person_id=10887: "
            'No parameter provided to function "getHansard". Possible choices are: search, person, order, page, num'
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
            result = await client.call_tool("search_hansard", {"query": "housing"})

        assert result.is_error
        assert result_text(result) == f"Error executing tool search_hansard: {message}"


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
