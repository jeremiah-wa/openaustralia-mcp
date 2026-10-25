import anyio
import httpx2

from openaustralia_mcp.config import Config
from openaustralia_mcp.server import VERSION, build_server

HTTP_TIMEOUT_SECONDS = 20


def main() -> None:
    anyio.run(_serve)


async def _serve() -> None:
    # Keys are read now but checked on first use, so the server always starts.
    async with httpx2.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": f"openaustralia-mcp/{VERSION}"},
    ) as http:
        await build_server(http, Config.from_env()).run_stdio_async()
