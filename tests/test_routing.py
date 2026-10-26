import pytest

from .conftest import Connect
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
