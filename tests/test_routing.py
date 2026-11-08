import httpx2
import pytest

from .conftest import Connect, result_text
from .fake_api import FakeApi

pytestmark = pytest.mark.anyio

API = "https://www.openaustralia.org.au/api"


class TestRoutedFixture:
    async def test_answers_the_request_it_was_recorded_for(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")

        async with connect() as client:
            result = await client.call_tool("get_members", {"postcode": "3056"})

        assert not result.is_error
        assert [member["name"] for member in result.structured_content["members"]] == ["Peter Khalil"]

    async def test_answers_each_request_from_its_own_fixture(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getRepresentatives_postcode_3056.json")
        fake_api.route("openaustralia/getRepresentatives_postcode_3181.json")

        async with connect() as client:
            khalil = await client.call_tool("get_members", {"postcode": "3056"})
            burns = await client.call_tool("get_members", {"postcode": "3181"})

        assert [member["name"] for member in khalil.structured_content["members"]] == ["Peter Khalil"]
        assert [member["name"] for member in burns.structured_content["members"]] == ["Josh Burns"]


class TestUnroutedRequest:
    async def test_gets_a_404_like_an_unknown_gid(self, connect: Connect, fake_api: FakeApi) -> None:
        # The same gid is recorded for the House only, so the Senate request has no fixture.
        fake_api.route("openaustralia/getDebates_representatives_2026-06-23.80.1.json")

        async with connect() as client:
            result = await client.call_tool("read_debate", {"gid": "2026-06-23.80.1", "house": "senate"})

        assert result.is_error
        assert "has no speech or debate with gid 2026-06-23.80.1 in the senate" in result_text(result)


class TestSearchKeywords:
    HOUSING_BY_10887 = "openaustralia/getHansard_search_housing_person_10887.json"

    async def test_answer_any_search_containing_a_keyword(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(self.HOUSING_BY_10887, search_contains=["housing", "rent"])

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "HOUSING affordability", "person_id": "10887"})

        assert not result.is_error
        assert result.structured_content["total_results"] == 69

    async def test_still_need_the_other_parameters_to_match(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(self.HOUSING_BY_10887, search_contains=["housing"])

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "housing"})

        assert result.is_error

    async def test_dont_answer_a_search_without_one(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(self.HOUSING_BY_10887, search_contains=["housing"])

        async with connect() as client:
            result = await client.call_tool("search_hansard", {"query": "immigration", "person_id": "10887"})

        assert result.is_error


class TestPartOfAValue:
    # No server tool takes a party yet, so these call the fake API directly.
    GREENS_SENATORS = "openaustralia/getSenators_party_Greens.json"

    def test_answer_any_value_that_is_part_of_the_text(self, fake_api: FakeApi) -> None:
        # OpenAustralia answers a party that is part of the party's name, ignoring case.
        fake_api.route(self.GREENS_SENATORS, part_of={"party": ["Australian Greens"]})

        statuses = [
            fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "party": party})).status_code
            for party in ("Australian Greens", "Greens", "green")
        ]

        assert statuses == [200, 200, 200]

    def test_dont_answer_a_value_that_isnt(self, fake_api: FakeApi) -> None:
        # OpenAustralia returns no one for "The Greens", so the fixture mustn't answer it either.
        fake_api.route(self.GREENS_SENATORS, part_of={"party": ["Australian Greens"]})

        statuses = [
            fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "party": party})).status_code
            for party in ("The Greens", "Labor")
        ]

        assert statuses == [404, 404]

    def test_still_need_the_other_parameters_to_match(self, fake_api: FakeApi) -> None:
        fake_api.route(self.GREENS_SENATORS, part_of={"party": ["Australian Greens"]})

        response = fake_api(
            httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "party": "Greens", "state": "Tasmania"})
        )

        assert response.status_code == 404

    def test_a_value_must_be_part_of_every_text(self, fake_api: FakeApi) -> None:
        # A name search returns the members whose name the value is part of: "Pocock" gets both Senators,
        # and "David Pocock" only one. So each fixture lists the names it holds, and the first that fits answers.
        fake_api.route(
            "openaustralia/getSenators_search_Pocock.json", part_of={"search": ["Barbara Pocock", "David Pocock"]}
        )
        fake_api.route("openaustralia/getSenators_search_David_Pocock.json", part_of={"search": ["David Pocock"]})

        def senators(search: str) -> list[str]:
            response = fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "search": search}))
            return [senator["full_name"] for senator in response.json()]

        assert senators("pocock") == ["Barbara Pocock", "David Pocock"]
        assert senators("David Pocock") == ["David Pocock"]


class TestGivenResponse:
    # For a response that can't be recorded, such as a failure. These call the fake API directly.
    def test_answers_its_request(self, fake_api: FakeApi) -> None:
        fake_api.answer("getSenators", {}, httpx2.Response(502))

        response = fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "output": "js"}))

        assert response.status_code == 502

    def test_needs_the_parameters_to_match(self, fake_api: FakeApi) -> None:
        fake_api.answer("getSenators", {}, httpx2.Response(502))

        response = fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k", "state": "Tasmania"}))

        assert response.status_code == 404

    def test_works_alongside_recorded_responses(self, fake_api: FakeApi) -> None:
        fake_api.route("openaustralia/getSenator_id_10942.json")
        fake_api.answer("getSenators", {}, httpx2.Response(502))

        senator = fake_api(httpx2.Request("GET", f"{API}/getSenator", params={"key": "k", "id": "10942"}))
        senators = fake_api(httpx2.Request("GET", f"{API}/getSenators", params={"key": "k"}))

        assert (senator.status_code, senator.json()[0]["full_name"]) == (200, "Dave Sharma")
        assert senators.status_code == 502

    async def test_answers_every_time_it_is_asked(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.answer("getSenators", {"state": "Tasmania"}, httpx2.Response(200, json=[]))

        async with connect() as client:
            first = await client.call_tool("get_members", {"state": "TAS"})
            second = await client.call_tool("get_members", {"state": "TAS"})

        no_one = (
            "Error executing tool get_members: OpenAustralia has no current member matching state=TAS. "
            "Searches find current members only. For a former member, find their person_id, for example on a "
            "search_hansard hit, and look them up by that."
        )
        assert [result_text(first), result_text(second)] == [no_one, no_one]
