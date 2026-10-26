from collections.abc import Callable
from pathlib import Path

import httpx2

FIXTURES = Path(__file__).parent / "fixtures"

# What OpenAustralia actually sends.
OA_HEADERS = {"content-type": "text/javascript; charset=iso-8859-1"}

Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeApi:
    """Stands in for the remote API: answers from recorded responses and keeps the requests it received."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self._handler: Handler = lambda request: httpx2.Response(599)

    def serve_fixture(self, name: str) -> None:
        body = (FIXTURES / name).read_bytes()
        self._handler = lambda request: httpx2.Response(200, content=body, headers=OA_HEADERS)

    def serve(self, handler: Handler) -> None:
        self._handler = handler

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._handler(request)
