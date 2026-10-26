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
    "openaustralia/getHansard_person_10887.json": RecordedRequest("getHansard", {"person": "10887"}),
    "openaustralia/getHansard_search_housing_person_10887.json": RecordedRequest(
        "getHansard", {"search": "housing", "person": "10887"}
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
    "openaustralia/getDebates_senate_2026-10-15.118.1.json": RecordedRequest(
        "getDebates", {"type": "senate", "gid": "2026-10-15.118.1"}
    ),
}


class FakeApi:
    """Stands in for the remote API: answers from recorded responses and keeps the requests it received."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self._handler: Handler = lambda request: httpx2.Response(599)
        self._routes: list[tuple[RecordedRequest, bytes]] = []

    def serve_fixture(self, name: str) -> None:
        """Answers every request with this recorded response."""
        body = (FIXTURES / name).read_bytes()
        self._handler = lambda request: httpx2.Response(200, content=body, headers=OA_HEADERS)

    def route(self, name: str) -> None:
        """Answers the request this response was recorded for (see `RECORDED`). Can be called once per fixture.

        Any request without a routed fixture gets an HTTP 404.
        """
        self._routes.append((RECORDED[name], (FIXTURES / name).read_bytes()))
        self._handler = self._answer_routed

    def serve(self, handler: Handler) -> None:
        self._handler = handler

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._handler(request)

    def _answer_routed(self, request: httpx2.Request) -> httpx2.Response:
        function = request.url.path.rsplit("/", 1)[-1]
        params = {name: value for name, value in request.url.params.items() if name not in ("key", "output")}
        for recorded, body in self._routes:
            if recorded.function == function and recorded.params == params:
                return httpx2.Response(200, content=body, headers=OA_HEADERS)
        # The server reports it as a tool error and Claude carries on, as for an unknown gid.
        return httpx2.Response(404)
