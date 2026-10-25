import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server

FIXTURES = Path(__file__).parent / "fixtures"

# Stands in for a real key. Tests check it never shows up in a result or a log.
TEST_KEY = "TEST-KEY-not-real"
TEST_CONFIG = Config(openaustralia_api_key=TEST_KEY)

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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi()


Connect = Callable[..., AbstractAsyncContextManager[Client]]


@pytest.fixture
def connect(fake_api: FakeApi) -> Connect:
    """Connects an in-memory MCP client to a server whose HTTP goes to `fake_api`."""

    @asynccontextmanager
    async def _connect(config: Config = TEST_CONFIG) -> AsyncIterator[Client]:
        async with (
            httpx2.AsyncClient(transport=httpx2.MockTransport(fake_api)) as http,
            Client(build_server(http, config)) as client,
        ):
            yield client

    return _connect


def result_text(result: CallToolResult) -> str:
    """Everything the model would see from a tool call."""
    texts = [block.text for block in result.content if hasattr(block, "text")]
    if result.structured_content is not None:
        texts.append(json.dumps(result.structured_content))
    return "\n".join(texts)
