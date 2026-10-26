import pytest

from .conftest import Connect, result_text
from .fake_api import FakeApi

pytestmark = pytest.mark.anyio


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
