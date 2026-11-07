"""search_hansard and read_debate: what was said in federal Parliament, and the shape of their results."""

import html
import re
from typing import Annotated

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from openaustralia_mcp.errors import ApiClientError, NotFoundError
from openaustralia_mcp.openaustralia import (
    HANSARD_LICENCE,
    SITE_URL,
    DebateEntry,
    HansardRow,
    HansardSearch,
    House,
)
from openaustralia_mcp.tools import Clients, ToolSet, _describe

# Characters of debate text per read_debate call.
DEBATE_PAGE_SIZE = 4000


class HansardHit(BaseModel):
    gid: str = Field(description="Identifies this speech in Hansard.")
    date: str
    house: House
    speaker: str
    person_id: str = Field(description="The speaker's person_id. Pass it to other tools.")
    debate: str = Field(description="Title of the debate the speech was part of.")
    excerpt: str = Field(description="The part of the speech that matched, as OpenAustralia excerpts it.")
    url: str = Field(description="The speech on OpenAustralia. Cite it.")

    @classmethod
    def from_row(cls, row: HansardRow) -> "HansardHit":
        return cls(
            gid=row.gid,
            date=row.hdate,
            house="senate" if row.major == "101" else "representatives",
            speaker=f"{row.speaker.first_name} {row.speaker.last_name}",
            person_id=row.speaker.person_id,
            debate=row.parent.body,
            excerpt=_plain_text(row.body),
            url=row.url,
        )


def _plain_text(markup: str) -> str:
    """Drops tags such as the search-term highlighting and decodes entities. The words are left as they are."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


class HansardSearchResult(BaseModel):
    hits: list[HansardHit]
    total_results: int = Field(description="How many speeches matched in all, including those not returned.")
    source_url: str
    licence: str

    @classmethod
    def from_search(cls, search: HansardSearch) -> "HansardSearchResult":
        return cls(
            hits=[HansardHit.from_row(row) for row in search.rows],
            total_results=search.info.total_results,
            source_url=SITE_URL,
            licence=HANSARD_LICENCE,
        )


class DebateResult(BaseModel):
    gid: str
    house: House
    date: str
    debate: str = Field(description="Title of the debate.")
    url: str = Field(description="The speech or debate on OpenAustralia. Cite it.")
    text: str = Field(description="One page of the speech(es) as Hansard records them, each after the speaker's name.")
    offset: int = Field(description="Where this page starts in the full text.")
    next_offset: int | None = Field(description="Pass as offset to read the next page. None on the last page.")
    total_length: int = Field(description="Length of the full text in characters.")
    source_url: str
    licence: str

    @classmethod
    def from_entries(cls, entries: list[DebateEntry], gid: str, house: House, offset: int) -> "DebateResult":
        [requested] = [entry for entry in entries if entry.gid == gid]
        # A speech gid brings just that speech. A heading gid brings every speech under it.
        text = "\n\n".join(_speech_text(entry) for entry in entries if not entry.is_heading)
        end = offset + DEBATE_PAGE_SIZE
        return cls(
            gid=gid,
            house=house,
            date=requested.hdate,
            # Section and subsection headings, the same title getHansard gives as `parent.body`.
            debate=": ".join(entry.body for entry in entries if entry.is_heading),
            url=requested.url,
            text=text[offset:end],
            offset=offset,
            next_offset=end if len(text) > end else None,
            total_length=len(text),
            source_url=SITE_URL,
            licence=HANSARD_LICENCE,
        )


def _speech_text(entry: DebateEntry) -> str:
    """The speaker's name on its own line, then the speech, with a blank line between paragraphs."""
    text = _plain_text(re.sub(r"</p>\s*<p[^>]*>", "\n\n", entry.body)).strip()
    if entry.speaker is None:
        return text
    return f"{entry.speaker.first_name} {entry.speaker.last_name}:\n\n{text}"


tools = ToolSet()


@tools.tool
async def search_hansard(
    ctx: Context[Clients],
    query: Annotated[
        str | None, Field(min_length=1, description='Words to search for, e.g. "housing affordability".')
    ] = None,
    person_id: Annotated[
        str | None,
        Field(pattern=r"^\d+$", description="Only speeches by this member. Get it from get_members."),
    ] = None,
) -> HansardSearchResult:
    """Search what was said in federal Parliament (Hansard), in both the House and the Senate.

    Returns the 20 most recent matching speeches, each with the speaker, date, debate title, a short
    excerpt, a gid and a url to the full speech.
    """
    openaustralia = ctx.request_context.lifespan_context.openaustralia
    if query is None and person_id is None:
        raise ToolError("Give a query, a person_id, or both.")
    try:
        search = await openaustralia.search_hansard(query, person_id)
    except ApiClientError as exc:
        raise ToolError(_describe(exc, query=query, person_id=person_id)) from None
    return HansardSearchResult.from_search(search)


@tools.tool
async def read_debate(
    ctx: Context[Clients],
    gid: Annotated[
        str,
        Field(
            pattern=r"^\d{4}-\d{2}-\d{2}\.\d+\.\d+$",
            description="A speech's gid, from search_hansard. Or, to read the whole debate, the id= in its url.",
        ),
    ],
    house: Annotated[
        House,
        Field(description="The house the gid is from, as search_hansard gives it. gids repeat across houses."),
    ],
    offset: Annotated[int, Field(ge=0, description="Where to start reading. Pass next_offset from the last call.")] = 0,
) -> DebateResult:
    """Read the full text of a speech or debate in federal Parliament (Hansard), by its gid and house.

    Each speech starts with the speaker's name on its own line. Returns up to 4,000 characters at a
    time. Pass next_offset as offset to read on.
    """
    openaustralia = ctx.request_context.lifespan_context.openaustralia
    try:
        entries = await openaustralia.get_debates(house, gid)
    except NotFoundError:
        raise ToolError(
            f"OpenAustralia has no speech or debate with gid {gid} in the {house}. "
            "Check that house matches the search_hansard hit the gid came from."
        ) from None
    except ApiClientError as exc:
        raise ToolError(_describe(exc, gid=gid, house=house)) from None
    result = DebateResult.from_entries(entries, gid, house, offset)
    if offset > 0 and offset >= result.total_length:
        raise ToolError(
            f"offset {offset} is past the end of the text, which is {result.total_length} characters long. "
            "Start from 0, or pass next_offset from the last call."
        )
    return result
