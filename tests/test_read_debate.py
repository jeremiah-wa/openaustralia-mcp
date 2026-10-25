import pytest

from .conftest import TEST_KEY, Connect, FakeApi, result_text

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

        # In the fixture: `...in a quarter of a century.</p><p>We've delivered this...`, within the first page.
        assert (
            "probably the most significant in a quarter of a century.\n\nWe've delivered this because"
            in result.structured_content["text"]
        )


class TestPaging:
    async def test_returns_the_first_4000_characters(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        # The speech alone is 8,715 characters as plain text.
        content = result.structured_content
        assert len(content["text"]) == 4000
        assert content["offset"] == 0
        assert content["next_offset"] == 4000
        assert content["total_length"] > 8715

    async def test_follows_next_offset_to_the_end_of_the_speech(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        pages = []
        offset: int | None = 0
        async with connect() as client:
            # Bounded, so a next_offset that never becomes None fails the test instead of hanging it.
            while offset is not None and len(pages) < 5:
                result = await client.call_tool("read_debate", {**KHALIL_ARGS, "offset": offset})
                assert not result.is_error
                pages.append(result.structured_content)
                offset = result.structured_content["next_offset"]

        assert [page["offset"] for page in pages] == [0, 4000, 8000]
        # The fixture's body ends `...lay out the facts today.</p> `.
        assert pages[-1]["text"].endswith("This is why it's so important to lay out the facts today.")
        assert len("".join(page["text"] for page in pages)) == pages[0]["total_length"]

    async def test_explains_an_offset_past_the_end(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture(KHALIL)

        async with connect() as client:
            first = await client.call_tool("read_debate", KHALIL_ARGS)
            result = await client.call_tool("read_debate", {**KHALIL_ARGS, "offset": 100000})

        total_length = first.structured_content["total_length"]
        assert result.is_error
        assert result_text(result) == (
            f"Error executing tool read_debate: offset 100000 is past the end of the text, "
            f"which is {total_length} characters long. Start from 0, or pass next_offset from the last call."
        )


class TestSenate:
    async def test_reads_a_senate_speech(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getDebates_senate_2026-10-15.118.1.json")

        async with connect() as client:
            result = await client.call_tool("read_debate", {"gid": "2026-10-15.118.1", "house": "senate"})

        [request] = fake_api.requests
        assert request.url.params["type"] == "senate"
        content = result.structured_content
        assert content["house"] == "senate"
        assert content["url"] == "https://www.openaustralia.org.au/senate/?id=2026-10-15.117.1#g118.1"
        assert content["text"].startswith("Jenny McAllister:\n\n")
