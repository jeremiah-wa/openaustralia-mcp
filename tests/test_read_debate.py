import pytest

from .conftest import TEST_KEY, Connect, FakeApi

pytestmark = pytest.mark.anyio

KHALIL = "openaustralia/getDebates_representatives_2026-06-23.80.1.json"
KHALIL_ARGS = {"gid": "2026-06-23.80.1", "house": "representatives"}


class TestDebateRequest:
    async def test_asks_openaustralia_for_the_gid_in_that_house(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        assert not result.is_error
        [request] = fake_api.requests
        assert str(request.url).startswith("https://www.openaustralia.org.au/api/getDebates?")
        assert dict(request.url.params) == {
            "key": TEST_KEY,
            "output": "js",
            "type": "representatives",
            "gid": "2026-06-23.80.1",
        }
        assert result.structured_content["source_url"] == "https://www.openaustralia.org.au"
        assert result.structured_content["licence"] == (
            "Hansard: Commonwealth of Australia, CC BY-NC-ND 3.0 AU (https://creativecommons.org/licenses/by-nc-nd/3.0/au/)"
        )


class TestDebateResult:
    async def test_returns_the_debate_title_date_and_link(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        content = result.structured_content
        assert content["gid"] == "2026-06-23.80.1"
        assert content["house"] == "representatives"
        assert content["date"] == "2026-06-23"
        # The same title search_hansard gives this speech.
        assert content["debate"] == "Matters of Public Importance: Budget"
        assert content["url"] == "https://www.openaustralia.org.au/debates/?id=2026-06-23.78.2#g80.1"

    async def test_returns_the_speech_after_the_speakers_name(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        # The fixture's body starts `<p>'Hyperbole'&#8212;I looked up`.
        text = result.structured_content["text"]
        assert text.startswith(
            "Peter Khalil:\n\n'Hyperbole'—I looked up the definition in the dictionary: 'a figure of speech or a "
            "statement that uses extreme, deliberate exaggeration to make a point, emphasise emotion or create humour'."
        )
        assert "<p>" not in text
        assert "&#8212;" not in text

    async def test_keeps_paragraph_breaks(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        # In the fixture: `...in a quarter of a century.</p><p>We've delivered this...`
        assert (
            "probably the most significant in a quarter of a century.\n\nWe've delivered this because"
            in result.structured_content["text"]
        )
