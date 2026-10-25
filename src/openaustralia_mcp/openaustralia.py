"""Client for the OpenAustralia API (https://www.openaustralia.org.au/api/)."""

from typing import Any

import httpx2

from openaustralia_mcp.config import OPENAUSTRALIA_KEY_ENV
from openaustralia_mcp.errors import MissingKeyError

API_NAME = "OpenAustralia"
BASE_URL = "https://www.openaustralia.org.au/api"
KEY_URL = "https://www.openaustralia.org.au/api/key"


class OpenAustraliaClient:
    def __init__(self, http: httpx2.AsyncClient, api_key: str | None) -> None:
        self._http = http
        self._api_key = api_key

    async def get_representatives(self, postcode: str) -> list[dict[str, Any]]:
        """House of Representatives members whose electorate covers the postcode."""
        return await self._call("getRepresentatives", postcode=postcode)

    async def _call(self, function: str, **params: str) -> Any:
        if not self._api_key:
            raise MissingKeyError(API_NAME, OPENAUSTRALIA_KEY_ENV, KEY_URL)

        response = await self._http.get(
            f"{BASE_URL}/{function}",
            params={"key": self._api_key, "output": "js", **params},
        )
        return response.json()
