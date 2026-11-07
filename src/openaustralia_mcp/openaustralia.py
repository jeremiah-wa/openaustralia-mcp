"""Client for the OpenAustralia API (https://www.openaustralia.org.au/api/)."""

import html
from typing import Any, Literal

import httpx2
from pydantic import BaseModel, TypeAdapter, field_validator

from openaustralia_mcp.config import OPENAUSTRALIA_KEY_ENV
from openaustralia_mcp.errors import ApiError, ApiUnavailableError, KeyRejectedError, MissingKeyError, NotFoundError

API_NAME = "OpenAustralia"
SITE_URL = "https://www.openaustralia.org.au"
BASE_URL = f"{SITE_URL}/api"
KEY_URL = f"{SITE_URL}/api/key"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
)
HANSARD_LICENCE = (
    "Hansard: Commonwealth of Australia, CC BY-NC-ND 3.0 AU (https://creativecommons.org/licenses/by-nc-nd/3.0/au/)"
)

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
    left_house: str = STILL_CURRENT
    office: list[Office] = []

    @property
    def is_current(self) -> bool:
        return self.left_house == STILL_CURRENT

    @property
    def current_positions(self) -> list[str]:
        return [office.position for office in self.office if office.position and office.to_date == STILL_CURRENT]

    @property
    def url(self) -> str:
        """The member's page on OpenAustralia."""
        return f"{SITE_URL}/mp/?p={self.person_id}"


# The list holds `false` for a division OpenAustralia has no current member for,
# such as an electorate abolished in a redistribution that its postcode data still includes.
Representatives = list[Representative | Literal[False]]
_representatives = TypeAdapter(Representatives)
_representative_records = TypeAdapter(list[Representative])

House = Literal["representatives", "senate"]
State = Literal["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
# A spelling of each state that getSenators' `state` accepts. It takes TAS or Tasmania and VIC or Victoria, but only
# Queensland, not QLD, and only NSW, WA, SA, ACT and NT, not their full names.
STATE_SPELLINGS: dict[State, str] = {
    "NSW": "NSW",
    "VIC": "Victoria",
    "QLD": "Queensland",
    "WA": "WA",
    "SA": "SA",
    "TAS": "Tasmania",
    "ACT": "ACT",
    "NT": "NT",
}
# Senators' `constituency` uses the same mix of spellings.
_STATE_CODES = {spelling: code for code, spelling in STATE_SPELLINGS.items()} | {code: code for code in STATE_SPELLINGS}


class Senator(Representative):
    """A Senator as getSenator(s) returns them. `constituency` is their state or territory."""

    @property
    def state(self) -> str | None:
        """The state or territory as a code, such as TAS, whichever way OpenAustralia spells it."""
        return _STATE_CODES.get(self.constituency or "", self.constituency)

    @property
    def url(self) -> str:
        """The Senator's page on OpenAustralia."""
        return f"{SITE_URL}/senator/?p={self.person_id}"


_senator_records = TypeAdapter(list[Senator])

# What getRepresentative and getSenator say for a person who never sat in that house.
UNKNOWN_PERSON = "Unknown person ID"


class HansardSpeaker(BaseModel):
    person_id: str
    first_name: str
    last_name: str


class HansardParent(BaseModel):
    body: str


class HansardRow(BaseModel):
    """A speech as getHansard returns it, with OpenAustralia's field names. Other fields are ignored."""

    gid: str
    hdate: str
    major: Literal["1", "101"]  # House of Representatives debates, Senate debates
    body: str
    listurl: str
    speaker: HansardSpeaker
    parent: HansardParent

    @property
    def url(self) -> str:
        """The speech on OpenAustralia."""
        return _site_url(self.listurl)


class HansardInfo(BaseModel):
    total_results: int


class HansardSearch(BaseModel):
    info: HansardInfo
    rows: list[HansardRow]

    @field_validator("rows", mode="before")
    @classmethod
    def _no_rows(cls, rows: Any) -> Any:
        # With no hits, OpenAustralia sends `{}` (an empty PHP array) rather than `[]`.
        return [] if rows == {} else rows


class DebateEntry(BaseModel):
    """A heading or speech as getDebates returns it, with OpenAustralia's field names. Other fields are ignored."""

    gid: str
    htype: str  # "10" section heading, "11" subsection heading, "12" speech
    hdate: str
    body: str
    listurl: str
    speaker: HansardSpeaker | None = None

    @field_validator("speaker", mode="before")
    @classmethod
    def _no_speaker(cls, speaker: Any) -> Any:
        # Headings come with `{}` (an empty PHP array) or no speaker at all.
        return None if speaker == {} else speaker

    @property
    def is_heading(self) -> bool:
        return self.htype in ("10", "11")

    @property
    def url(self) -> str:
        """The speech or debate on OpenAustralia."""
        return _site_url(self.listurl)


_debate_entries = TypeAdapter(list[DebateEntry])


def _none_found(data: Any) -> Any:
    # With no members to send, OpenAustralia sends `{}` (an empty PHP array) rather than `[]`.
    return [] if data == {} else data


def _given(**params: str | None) -> dict[str, str]:
    """The parameters that have a value. OpenAustralia treats an empty parameter differently from a missing one."""
    return {name: value for name, value in params.items() if value is not None}


def _site_url(listurl: str) -> str:
    # listurl is relative and HTML-escaped (`&amp;`).
    return SITE_URL + html.unescape(listurl)


class OpenAustraliaClient:
    def __init__(self, http: httpx2.AsyncClient, api_key: str | None) -> None:
        self._http = http
        self._api_key = api_key

    async def get_representatives(
        self, postcode: str | None = None, *, party: str | None = None, search: str | None = None
    ) -> Representatives:
        """Current House of Representatives members whose electorate covers the postcode, or who match the rest.

        OpenAustralia matches part of a party's name, or of a member's full name, ignoring case: "greens" gets the
        Australian Greens, and "khalil" or "Peter Khalil" gets Peter Khalil.
        """
        given = _given(postcode=postcode, party=party, search=search)
        return _representatives.validate_python(_none_found(await self._call("getRepresentatives", **given)))

    async def get_senators(
        self, *, state: State | None = None, party: str | None = None, search: str | None = None
    ) -> list[Senator]:
        """Current Senators who match every filter given, matched as for get_representatives."""
        given = _given(state=STATE_SPELLINGS[state] if state else None, party=party, search=search)
        return _senator_records.validate_python(_none_found(await self._call("getSenators", **given)))

    async def get_representative(self, person_id: str) -> list[Representative]:
        """The person's records as a member of the House, current or former. Empty if they never sat in it."""
        return _representative_records.validate_python(await self._person("getRepresentative", person_id))

    async def get_senator(self, person_id: str) -> list[Senator]:
        """The person's records as a Senator, current or former. Empty if they never sat in the Senate."""
        return _senator_records.validate_python(await self._person("getSenator", person_id))

    async def _person(self, function: str, person_id: str) -> Any:
        try:
            return await self._call(function, id=person_id)
        except ApiError as exc:
            if exc.message == UNKNOWN_PERSON:
                return []
            raise

    async def search_hansard(self, search: str | None = None, person: str | None = None) -> HansardSearch:
        """Speeches in either house that match the search and/or are by the person, newest first, 20 to a page."""
        given = _given(search=search, person=person)
        return HansardSearch.model_validate(await self._call("getHansard", **given))

    async def get_debates(self, type: House, gid: str) -> list[DebateEntry]:
        """The headings and speech(es) for a gid. gids repeat across houses, so the type picks the house."""
        return _debate_entries.validate_python(await self._call("getDebates", type=type, gid=gid))

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
        if response.status_code == 404:
            raise NotFoundError(API_NAME)
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
