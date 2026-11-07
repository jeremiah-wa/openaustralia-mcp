import json
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import build_server

from .fake_api import FakeApi

# Stands in for a real key. Tests check it never shows up in a result or a log.
TEST_KEY = "TEST-KEY-not-real"
TEST_CONFIG = Config(openaustralia_api_key=TEST_KEY)


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
    async def _connect(config: Config = TEST_CONFIG) -> AsyncGenerator[Client]:
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
