from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures"

# What OpenAustralia actually sends.
OA_HEADERS = {"content-type": "text/javascript; charset=iso-8859-1"}

Handler = Callable[[httpx2.Request], httpx2.Response]


@dataclass(frozen=True)
class RecordedRequest:
    function: str
    params: dict[str, str]


# The request each recorded response answers, without `key` and `output`.
# The error fixtures aren't here: they answer any request, through `serve_fixture`.
RECORDED = {
    "openaustralia/getRepresentatives_postcode_0000.json": RecordedRequest("getRepresentatives", {"postcode": "0000"}),
    "openaustralia/getRepresentatives_postcode_3056.json": RecordedRequest("getRepresentatives", {"postcode": "3056"}),
    "openaustralia/getRepresentatives_postcode_3142.json": RecordedRequest("getRepresentatives", {"postcode": "3142"}),
    "openaustralia/getRepresentatives_postcode_3181.json": RecordedRequest("getRepresentatives", {"postcode": "3181"}),
    # Neighbours of 3142, which Claude tries when 3142 has no current member.
    "openaustralia/getRepresentatives_postcode_3143.json": RecordedRequest("getRepresentatives", {"postcode": "3143"}),
    "openaustralia/getRepresentatives_postcode_3144.json": RecordedRequest("getRepresentatives", {"postcode": "3144"}),
    "openaustralia/getRepresentatives_postcode_3146.json": RecordedRequest("getRepresentatives", {"postcode": "3146"}),
    "openaustralia/getRepresentatives_search_Khalil.json": RecordedRequest("getRepresentatives", {"search": "Khalil"}),
    # Name searches that find no one get `{}`.
    "openaustralia/getSenators_search_Khalil.json": RecordedRequest("getSenators", {"search": "Khalil"}),
    "openaustralia/getRepresentatives_search_Pocock.json": RecordedRequest("getRepresentatives", {"search": "Pocock"}),
    "openaustralia/getRepresentatives_party_Greens.json": RecordedRequest("getRepresentatives", {"party": "Greens"}),
    # OpenAustralia takes TAS or Tasmania, but QLD fails where Queensland works, and NSW works where New South Wales
    # fails. The member tools send one spelling that works for each state.
    "openaustralia/getSenators_state_Tasmania.json": RecordedRequest("getSenators", {"state": "Tasmania"}),
    "openaustralia/getSenators_party_Greens.json": RecordedRequest("getSenators", {"party": "Greens"}),
    "openaustralia/getSenators_search_Pocock.json": RecordedRequest("getSenators", {"search": "Pocock"}),
    "openaustralia/getSenators_search_David_Pocock.json": RecordedRequest("getSenators", {"search": "David Pocock"}),
    "openaustralia/getHansard_person_10887.json": RecordedRequest("getHansard", {"person": "10887"}),
    "openaustralia/getHansard_search_housing_person_10887.json": RecordedRequest(
        "getHansard", {"search": "housing", "person": "10887"}
    ),
    "openaustralia/getHansard_search_housing_person_11009.json": RecordedRequest(
        "getHansard", {"search": "housing", "person": "11009"}
    ),
    "openaustralia/getHansard_search_ndis.json": RecordedRequest("getHansard", {"search": "NDIS"}),
    "openaustralia/getHansard_search_no_results.json": RecordedRequest(
        "getHansard", {"search": "xyzzyplughnonsenseword"}
    ),
    "openaustralia/getDebates_representatives_2026-06-23.78.2.json": RecordedRequest(
        "getDebates", {"type": "representatives", "gid": "2026-06-23.78.2"}
    ),
    "openaustralia/getDebates_representatives_2026-06-23.80.1.json": RecordedRequest(
        "getDebates", {"type": "representatives", "gid": "2026-06-23.80.1"}
    ),
    "openaustralia/getDebates_senate_2026-06-23.80.1.json": RecordedRequest(
        "getDebates", {"type": "senate", "gid": "2026-06-23.80.1"}
    ),
    "openaustralia/getDebates_senate_2026-10-15.118.1.json": RecordedRequest(
        "getDebates", {"type": "senate", "gid": "2026-10-15.118.1"}
    ),
}


class FakeApi:
    """Stands in for the remote API: answers from recorded responses and keeps the requests it received."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self._handler: Handler = lambda request: httpx2.Response(599)
        self._routes: list[tuple[RecordedRequest, list[str] | None, dict[str, list[str]], bytes]] = []

    def serve_fixture(self, name: str) -> None:
        """Answers every request with this recorded response."""
        body = (FIXTURES / name).read_bytes()
        self._handler = lambda request: httpx2.Response(200, content=body, headers=OA_HEADERS)

    def route(
        self,
        name: str,
        *,
        search_contains: list[str] | None = None,
        part_of: dict[str, list[str]] | None = None,
    ) -> None:
        """Answers the request this response was recorded for (see `RECORDED`). Can be called once per fixture.

        With `search_contains`, it answers any `search` that contains one of the keywords, ignoring case.
        With `part_of`, it answers any value of each listed parameter that is part of every one of its texts,
        ignoring case, as OpenAustralia matches a party or a member's name: list the names the response holds.
        Either way, the other parameters must still match exactly.
        Any request without a routed fixture gets an HTTP 404.
        """
        self._routes.append((RECORDED[name], search_contains, part_of or {}, (FIXTURES / name).read_bytes()))
        self._handler = self._answer_routed

    def serve(self, handler: Handler) -> None:
        self._handler = handler

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._handler(request)

    def _answer_routed(self, request: httpx2.Request) -> httpx2.Response:
        function = request.url.path.rsplit("/", 1)[-1]
        params = {name: value for name, value in request.url.params.items() if name not in ("key", "output")}
        for recorded, search_contains, part_of, body in self._routes:
            if recorded.function == function and _matches(recorded.params, params, search_contains, part_of):
                return httpx2.Response(200, content=body, headers=OA_HEADERS)
        # The server reports it as a tool error and Claude carries on, as for an unknown gid.
        return httpx2.Response(404)


def _matches(
    recorded: dict[str, str], params: dict[str, str], search_contains: list[str] | None, part_of: dict[str, list[str]]
) -> bool:
    loose = set(part_of) | ({"search"} if search_contains is not None else set())
    if _without(recorded, loose) != _without(params, loose):
        return False
    if search_contains is not None:
        search = params.get("search", "").lower()
        if not any(keyword.lower() in search for keyword in search_contains):
            return False
    return all(
        (value := params.get(name, "").lower()) and all(value in text.lower() for text in texts)
        for name, texts in part_of.items()
    )


def _without(params: dict[str, str], names: set[str]) -> dict[str, str]:
    return {name: value for name, value in params.items() if name not in names}
