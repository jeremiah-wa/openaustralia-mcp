import logging

import httpx2
import pytest

from .conftest import TEST_KEY, Connect, result_text
from .fake_api import FakeApi, Handler

pytestmark = pytest.mark.anyio

KHALIL = "openaustralia/getDebates_representatives_2026-06-23.80.1.json"
KHALIL_ARGS = {"gid": "2026-06-23.80.1", "house": "representatives"}


class TestDebateRequest:
    async def test_asks_openaustralia_for_the_gid_in_that_house(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(KHALIL)

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
        fake_api.route(KHALIL)

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
        fake_api.route(KHALIL)

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
        fake_api.route(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        # In the fixture: `...in a quarter of a century.</p><p>We've delivered this...`, within the first page.
        assert (
            "probably the most significant in a quarter of a century.\n\nWe've delivered this because"
            in result.structured_content["text"]
        )


class TestPaging:
    async def test_returns_the_first_4000_characters(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        # The speech alone is 8,715 characters as plain text.
        content = result.structured_content
        assert len(content["text"]) == 4000
        assert content["offset"] == 0
        assert content["next_offset"] == 4000
        assert content["total_length"] > 8715

    async def test_follows_next_offset_to_the_end_of_the_speech(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.route(KHALIL)

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
        fake_api.route(KHALIL)

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
        fake_api.route("openaustralia/getDebates_senate_2026-10-15.118.1.json")

        async with connect() as client:
            result = await client.call_tool("read_debate", {"gid": "2026-10-15.118.1", "house": "senate"})

        [request] = fake_api.requests
        assert request.url.params["type"] == "senate"
        content = result.structured_content
        assert content["house"] == "senate"
        assert content["url"] == "https://www.openaustralia.org.au/senate/?id=2026-10-15.117.1#g118.1"
        assert content["text"].startswith("Jenny McAllister:\n\n")

    async def test_reads_the_senate_speech_for_a_gid_the_house_also_has(
        self, connect: Connect, fake_api: FakeApi
    ) -> None:
        # In the House, 2026-06-23.80.1 is Peter Khalil's speech on housing.
        fake_api.route("openaustralia/getDebates_senate_2026-06-23.80.1.json")
        fake_api.route(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", {"gid": "2026-06-23.80.1", "house": "senate"})

        assert result.structured_content["text"].startswith("Lidia Thorpe:\n\n")


class TestWholeDebate:
    async def test_reads_every_speech_under_a_heading_gid(self, connect: Connect, fake_api: FakeApi) -> None:
        # 2026-06-23.78.2 is the "Budget" heading, the `id=` in the url of each speech in the debate.
        fake_api.route("openaustralia/getDebates_representatives_2026-06-23.78.2.json")
        args = {"gid": "2026-06-23.78.2", "house": "representatives"}

        pages = []
        offset: int | None = 0
        async with connect() as client:
            while offset is not None and len(pages) < 20:
                result = await client.call_tool("read_debate", {**args, "offset": offset})
                assert not result.is_error
                pages.append(result.structured_content)
                offset = result.structured_content["next_offset"]

        assert pages[0]["debate"] == "Matters of Public Importance: Budget"
        assert pages[0]["url"] == "https://www.openaustralia.org.au/debates/?id=2026-06-23.78.2"
        # In fixture order. Melissa Price and Sharon Claydon speak twice.
        expected = [
            "Milton Dick",
            "Tim Wilson",
            "Peter Khalil",
            "Michael McCormack",
            "Ali France",
            "Anne Webster",
            "Jerome Laxale",
            "Melissa Price",
            "Sharon Claydon",
            "Melissa Price",
            "Carina Garland",
            "Tom Venning",
            "Alice Jordan-Baird",
            "Sharon Claydon",
        ]
        text = "".join(page["text"] for page in pages)
        name_lines = [line.removesuffix(":") for line in text.split("\n") if line.removesuffix(":") in expected]
        assert name_lines == expected
        assert text.startswith("Milton Dick:\n\n")


class TestNotFound:
    async def test_says_no_speech_has_that_gid_in_that_house(self, connect: Connect, fake_api: FakeApi) -> None:
        # What OpenAustralia sends for a gid it doesn't have: a 404 page, not an {"error": ...} body.
        fake_api.serve(lambda request: httpx2.Response(404, text="<!DOCTYPE html><html>...</html>"))

        async with connect() as client:
            result = await client.call_tool("read_debate", {"gid": "1999-01-01.1.1", "house": "senate"})

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool read_debate: OpenAustralia has no speech or debate with gid 1999-01-01.1.1 "
            "in the senate. Check that house matches the search_hansard hit the gid came from."
        )


class TestArguments:
    @pytest.mark.parametrize(
        ("arguments", "name"),
        [
            ({"gid": "abc", "house": "representatives"}, "gid"),
            ({"gid": "2026-06-23", "house": "representatives"}, "gid"),
            ({"gid": " 2026-06-23.80.1", "house": "representatives"}, "gid"),
            ({"gid": "", "house": "representatives"}, "gid"),
            ({"gid": 2026, "house": "representatives"}, "gid"),
            ({"gid": "2026-06-23.80.1", "house": "house"}, "house"),
            ({"gid": "2026-06-23.80.1"}, "house"),
            ({**KHALIL_ARGS, "offset": -1}, "offset"),
        ],
        ids=["word", "date-only", "leading-space", "empty", "number", "unknown-house", "no-house", "negative-offset"],
    )
    async def test_rejects_malformed_arguments_without_a_request(
        self, connect: Connect, fake_api: FakeApi, arguments: dict[str, object], name: str
    ) -> None:
        fake_api.route(KHALIL)

        async with connect() as client:
            result = await client.call_tool("read_debate", arguments)

        assert result.is_error
        assert name in result_text(result)
        assert fake_api.requests == []


class TestRejectedKey:
    async def test_says_the_key_was_rejected(self, connect: Connect, fake_api: FakeApi) -> None:
        fake_api.serve_fixture("openaustralia/getDebates_bad_key.json")

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool read_debate: The OpenAustralia key was rejected. "
            "Check it or get a new one at https://www.openaustralia.org.au/api/key."
        )


class TestApiError:
    async def test_passes_on_the_api_error_with_the_arguments(self, connect: Connect, fake_api: FakeApi) -> None:
        # Recorded from a call with type=nonsense, which the tool itself never makes.
        fake_api.serve_fixture("openaustralia/getDebates_unknown_type.json")

        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        assert result.is_error
        assert result_text(result) == (
            "Error executing tool read_debate: OpenAustralia returned an error for "
            "gid=2026-06-23.80.1, house=representatives: Unknown type"
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
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        assert result.is_error
        assert result_text(result) == f"Error executing tool read_debate: {message}"


def _connection_refused_naming_the_url(request: httpx2.Request) -> httpx2.Response:
    # Real HTTP errors mention the URL, and the URL contains the key.
    raise httpx2.ConnectError(f"connection refused: {request.url}", request=request)


LEAK_CASES = {
    "success": KHALIL,
    "rejected-key": "openaustralia/getDebates_bad_key.json",
    "api-error": "openaustralia/getDebates_unknown_type.json",
    "not-found": lambda request: httpx2.Response(404, text=f"<html>{request.url}</html>"),
    "connection-error": _connection_refused_naming_the_url,
    "server-error": lambda request: httpx2.Response(500),
}


class TestKeyNeverLeaks:
    @pytest.fixture(params=LEAK_CASES.values(), ids=LEAK_CASES.keys())
    def api_behaviour(self, request: pytest.FixtureRequest, fake_api: FakeApi) -> None:
        if isinstance(request.param, str):
            fake_api.serve_fixture(request.param)
        else:
            fake_api.serve(request.param)

    async def test_not_in_the_result(self, connect: Connect, api_behaviour: None) -> None:
        async with connect() as client:
            result = await client.call_tool("read_debate", KHALIL_ARGS)

        assert TEST_KEY not in result_text(result)

    async def test_not_in_the_logs(
        self, connect: Connect, api_behaviour: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)

        async with connect() as client:
            await client.call_tool("read_debate", KHALIL_ARGS)

        assert caplog.records, "expected some log output to check"
        assert TEST_KEY not in caplog.text
