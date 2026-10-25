"""Tool result models, and how raw API responses become them: small and citable."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SITE_URL = "https://www.openaustralia.org.au"
MEMBERS_LICENCE = (
    "Members data: OpenAustralia Foundation, CC BY-SA 2.5 (https://creativecommons.org/licenses/by-sa/2.5/)"
)

# OpenAustralia marks "still current" with this date, for members and for their offices.
STILL_CURRENT = "9999-12-31"


class Member(BaseModel):
    person_id: str = Field(description="Stable ID for this person. Pass it to other tools.")
    name: str
    party: str
    electorate: str
    house: Literal["representatives"]
    positions: list[str] = Field(description="Current ministerial or other offices, if any.")
    url: str = Field(description="The member's page on OpenAustralia. Cite it.")


class MembersResult(BaseModel):
    members: list[Member]
    note: str | None = Field(default=None, description="A caveat to pass on to the user, if any.")
    source_url: str
    licence: str


PARTIAL_MATCH_NOTE = (
    "OpenAustralia couldn't match part of this postcode to a current member, so this list may be incomplete. "
    "Its postcode data can lag behind changes to electorate boundaries."
)


def members_from_representatives(raw: list[Any]) -> MembersResult:
    # OpenAustralia puts `false` in the list for a division it has no current member for,
    # such as an electorate abolished in a redistribution that its postcode data still includes.
    found = [member for member in raw if isinstance(member, dict)]
    return MembersResult(
        members=[_member_from_representative(member) for member in found],
        note=PARTIAL_MATCH_NOTE if len(found) < len(raw) else None,
        source_url=SITE_URL,
        licence=MEMBERS_LICENCE,
    )


def _member_from_representative(raw: dict[str, Any]) -> Member:
    person_id = str(raw["person_id"])
    return Member(
        person_id=person_id,
        name=raw.get("full_name") or raw.get("name") or "",
        party=raw.get("party") or "",
        electorate=raw.get("constituency") or "",
        house="representatives",
        positions=[
            office["position"]
            for office in raw.get("office") or []
            if office.get("position") and office.get("to_date") == STILL_CURRENT
        ],
        url=f"{SITE_URL}/mp/?p={person_id}",
    )
