"""The eval graders are the eval's own logic, so they're tested directly (see docs/evals.md#graders)."""

from typing import Any

from evals.cases import Case
from evals.graders import Call, Trial, grade

# The tools' input schemas, cut down to their argument names.
SCHEMAS = {
    "get_members": {"properties": {"postcode": {}}},
    "search_hansard": {"properties": {"query": {}, "person_id": {}}},
    "read_debate": {"properties": {"gid": {}, "house": {}, "offset": {}}},
}

MEMBER_3056 = Call(
    tool="get_members",
    input={"postcode": "3056"},
    result={"members": [{"person_id": "10887", "url": "https://www.openaustralia.org.au/mp/?p=10887"}]},
)
HOUSING_BY_10887 = Call(tool="search_hansard", input={"query": "housing", "person_id": "10887"})


def case(question: str = "?", **expect: Any) -> Case:
    return Case.model_validate({"id": "test", "tags": ["regression"], "question": question, "expect": expect})


def trial(*calls: Call, answer: str = "") -> Trial:
    return Trial(calls=list(calls), answer=answer)


class TestExpectedCalls:
    def test_pass_when_the_call_is_made_with_those_arguments(self) -> None:
        expected = case(calls=[{"tool": "get_members", "args": {"postcode": "3056"}}])

        assert grade(expected, trial(MEMBER_3056), SCHEMAS) == []

    def test_fail_when_the_call_is_missing(self) -> None:
        expected = case(calls=[{"tool": "get_members", "args": {"postcode": "3056"}}])

        assert grade(expected, trial(), SCHEMAS) == ["missing call: get_members(postcode='3056')"]

    def test_fail_when_an_argument_has_another_value(self) -> None:
        expected = case(calls=[{"tool": "get_members", "args": {"postcode": "3181"}}])

        assert grade(expected, trial(MEMBER_3056), SCHEMAS) == ["missing call: get_members(postcode='3181')"]

    def test_ignore_arguments_the_case_doesnt_name(self) -> None:
        expected = case(calls=[{"tool": "search_hansard", "args": {"person_id": "10887"}}])

        assert grade(expected, trial(HOUSING_BY_10887), SCHEMAS) == []

    def test_match_args_contain_on_any_listed_text_ignoring_case(self) -> None:
        expected = case(calls=[{"tool": "search_hansard", "args_contain": {"query": ["rent", "HOUSING"]}}])

        assert grade(expected, trial(HOUSING_BY_10887), SCHEMAS) == []

    def test_fail_args_contain_when_no_listed_text_is_there(self) -> None:
        expected = case(calls=[{"tool": "search_hansard", "args_contain": {"query": ["NDIS"]}}])

        assert grade(expected, trial(HOUSING_BY_10887), SCHEMAS) == [
            "missing call: search_hansard(query contains one of ['NDIS'])"
        ]


MEMBER_THEN_SEARCH = [
    {"id": "member", "tool": "get_members", "args": {"postcode": "3056"}},
    {"tool": "search_hansard", "args": {"person_id": "10887"}, "after": "member"},
]


class TestDependencies:
    def test_pass_when_the_call_comes_after_the_one_it_needs(self) -> None:
        expected = case(calls=MEMBER_THEN_SEARCH)

        assert grade(expected, trial(MEMBER_3056, HOUSING_BY_10887), SCHEMAS) == []

    def test_fail_when_it_comes_before(self) -> None:
        expected = case(calls=MEMBER_THEN_SEARCH)

        assert grade(expected, trial(HOUSING_BY_10887, MEMBER_3056), SCHEMAS) == [
            "out of order: search_hansard(person_id='10887') came before member"
        ]

    def test_pass_when_a_matching_call_also_comes_later(self) -> None:
        expected = case(calls=MEMBER_THEN_SEARCH)

        assert grade(expected, trial(HOUSING_BY_10887, MEMBER_3056, HOUSING_BY_10887), SCHEMAS) == []

    def test_fail_when_one_call_matches_both(self) -> None:
        first_page = {"tool": "read_debate", "args": {"gid": "2026-06-23.78.2"}, "id": "first"}
        second_page = {"tool": "read_debate", "args": {"offset": 4000}, "after": "first"}
        only_page_two = Call(tool="read_debate", input={"gid": "2026-06-23.78.2", "offset": 4000})

        assert grade(case(calls=[first_page, second_page]), trial(only_page_two), SCHEMAS) == [
            "out of order: read_debate(offset=4000) came before first"
        ]


class TestForbiddenCalls:
    def test_fail_on_any_call_to_a_forbidden_tool(self) -> None:
        expected = case(forbidden=[{"tool": "get_members"}])

        assert grade(expected, trial(MEMBER_3056), SCHEMAS) == ["forbidden call: get_members(postcode='3056')"]

    def test_fail_only_when_the_forbidden_arguments_match(self) -> None:
        expected = case(forbidden=[{"tool": "read_debate", "args": {"house": "representatives"}}])
        senate = Call(tool="read_debate", input={"gid": "2026-06-23.80.1", "house": "senate"})
        house = Call(tool="read_debate", input={"gid": "2026-06-23.80.1", "house": "representatives"})

        assert grade(expected, trial(senate), SCHEMAS) == []
        assert grade(expected, trial(house), SCHEMAS) == [
            "forbidden call: read_debate(gid='2026-06-23.80.1', house='representatives')"
        ]

    def test_fail_when_the_listed_arguments_are_all_missing(self) -> None:
        expected = case(forbidden=[{"tool": "search_hansard", "args_missing": ["query", "person_id"]}])
        neither = Call(tool="search_hansard", input={})

        assert grade(expected, trial(neither), SCHEMAS) == ["forbidden call: search_hansard()"]
        assert grade(expected, trial(HOUSING_BY_10887), SCHEMAS) == []


class TestUnknownArguments:
    def test_fail_on_an_argument_the_tool_doesnt_have(self) -> None:
        # The server drops it silently, so this searches every member's speeches.
        misnamed = Call(tool="search_hansard", input={"query": "housing", "person": "10887"})

        assert grade(case(), trial(misnamed), SCHEMAS) == [
            "unknown argument: person in search_hansard(query='housing', person='10887')"
        ]

    def test_pass_when_every_argument_is_in_the_schema(self) -> None:
        page_two = Call(
            tool="read_debate", input={"gid": "2026-06-23.78.2", "house": "representatives", "offset": 4000}
        )

        assert grade(case(), trial(page_two), SCHEMAS) == []


class TestMaxCalls:
    def test_fail_when_there_are_more_calls_than_the_cap(self) -> None:
        assert grade(case(max_calls=1), trial(MEMBER_3056, HOUSING_BY_10887), SCHEMAS) == ["2 calls, more than 1"]

    def test_pass_at_the_cap(self) -> None:
        assert grade(case(max_calls=2), trial(MEMBER_3056, HOUSING_BY_10887), SCHEMAS) == []

    def test_zero_means_no_calls(self) -> None:
        assert grade(case(max_calls=0), trial(), SCHEMAS) == []
        assert grade(case(max_calls=0), trial(MEMBER_3056), SCHEMAS) == ["1 calls, more than 0"]


class TestAnswerContains:
    def test_pass_when_the_answer_has_each_text_ignoring_case(self) -> None:
        answer = "Your MP is PETER KHALIL, the member for Wills."

        assert grade(case(answer_contains=["Peter Khalil", "Wills"]), trial(answer=answer), SCHEMAS) == []

    def test_fail_for_each_missing_text(self) -> None:
        answer = "Your MP is Peter Khalil."

        assert grade(case(answer_contains=["Peter Khalil", "Wills"]), trial(answer=answer), SCHEMAS) == [
            "answer is missing: Wills"
        ]


class TestCitesUrl:
    def test_pass_when_the_answer_has_a_url_from_a_result(self) -> None:
        answer = "Peter Khalil (https://www.openaustralia.org.au/mp/?p=10887)"

        assert grade(case(cites_url=True), trial(MEMBER_3056, answer=answer), SCHEMAS) == []

    def test_fail_when_it_has_none(self) -> None:
        answer = "Peter Khalil"

        assert grade(case(cites_url=True), trial(MEMBER_3056, answer=answer), SCHEMAS) == [
            "answer cites no url from a tool result"
        ]

    def test_dont_count_the_source_url(self) -> None:
        # Every result has it, so citing it says nothing about the result.
        with_source = Call(tool="get_members", input={"postcode": "3056"}, result={"source_url": "https://oa.example"})

        assert grade(case(cites_url=True), trial(with_source, answer="See https://oa.example"), SCHEMAS) == [
            "answer cites no url from a tool result"
        ]

    def test_find_urls_nested_in_hits(self) -> None:
        url = "https://www.openaustralia.org.au/debates/?id=2026-06-23.78.1#g80.1"
        hits = Call(tool="search_hansard", input={"query": "housing"}, result={"hits": [{"gid": "1", "url": url}]})

        assert grade(case(cites_url=True), trial(hits, answer=f"[speech]({url})"), SCHEMAS) == []

    def test_pass_when_the_answer_has_the_url_the_user_pasted(self) -> None:
        # The tool links the speech within its debate, and the user's link is to the same speech.
        pasted = "https://www.openaustralia.org.au/debates/?id=2026-06-23.80.1"
        read = Call(
            tool="read_debate",
            input={"gid": "2026-06-23.80.1", "house": "representatives"},
            result={"url": "https://www.openaustralia.org.au/debates/?id=2026-06-23.78.2#g80.1"},
        )

        with_link = case(question=f"Can you read this speech? {pasted}", cites_url=True)
        assert grade(with_link, trial(read, answer=f"Peter Khalil's speech: {pasted}"), SCHEMAS) == []


class TestTurnCap:
    def test_fail_a_trial_that_hit_it(self) -> None:
        capped = Trial(calls=[MEMBER_3056], answer="", hit_turn_cap=True)

        assert grade(case(), capped, SCHEMAS) == ["hit the turn cap without answering"]

    def test_pass_a_trial_that_answered(self) -> None:
        assert grade(case(), trial(MEMBER_3056, answer="Peter Khalil"), SCHEMAS) == []
