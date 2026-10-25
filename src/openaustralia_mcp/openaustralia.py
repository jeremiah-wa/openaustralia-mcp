"""Client for the OpenAustralia API (https://www.openaustralia.org.au/api/)."""

from typing import Any, Literal

import httpx2
from pydantic import BaseModel, TypeAdapter

from openaustralia_mcp.config import OPENAUSTRALIA_KEY_ENV
from openaustralia_mcp.errors import ApiError, ApiUnavailableError, KeyRejectedError, MissingKeyError

API_NAME = "OpenAustralia"
BASE_URL = "https://www.openaustralia.org.au/api"
KEY_URL = "https://www.openaustralia.org.au/api/key"

# OpenAustralia marks "still current" with this date, for members and for their offices.
STILL_CURRENT = "9999-12-31"


class Office(BaseModel):
    position: str = ""
    to_date: str = ""


class Representative(BaseModel):
    """A member as getRepresentatives returns them, with OpenAustralia's field names. Other fields are ignored."""

    person_id: str
    full_name: str
    party: str | None = None
    constituency: str | None = None
    office: list[Office] = []

    @property
    def current_positions(self) -> list[str]:
        return [office.position for office in self.office if office.position and office.to_date == STILL_CURRENT]


# The list holds `false` for a division OpenAustralia has no current member for,
# such as an electorate abolished in a redistribution that its postcode data still includes.
Representatives = list[Representative | Literal[False]]
_representatives = TypeAdapter(Representatives)


class OpenAustraliaClient:
    def __init__(self, http: httpx2.AsyncClient, api_key: str | None) -> None:
        self._http = http
        self._api_key = api_key

    async def get_representatives(self, postcode: str) -> Representatives:
        """House of Representatives members whose electorate covers the postcode."""
        return _representatives.validate_python(await self._call("getRepresentatives", postcode=postcode))

    async def _call(self, function: str, **params: str) -> Any:
        if not self._api_key:
            raise MissingKeyError(API_NAME, OPENAUSTRALIA_KEY_ENV, KEY_URL)

        # `from None` throughout: the HTTP error's context holds the URL, and the URL holds the key.
        try:
            response = await self._http.get(
                f"{BASE_URL}/{function}",
                params={"key": self._api_key, "output": "js", **params},
            )
        except httpx2.HTTPError:
            raise ApiUnavailableError(API_NAME) from None
        if response.status_code != 200:
            raise ApiUnavailableError(API_NAME, response.status_code)
        try:
            data = response.json()
        except ValueError:
            raise ApiUnavailableError(API_NAME, response.status_code) from None

        # Errors come back as HTTP 200 with a body like {"error": "Invalid API key."}.
        if isinstance(data, dict) and "error" in data:
            message = str(data["error"])
            if "api key" in message.lower():
                raise KeyRejectedError(API_NAME, KEY_URL)
            raise ApiError(API_NAME, message)
        return data
