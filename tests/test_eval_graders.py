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


def case(**expect: Any) -> Case:
    return Case.model_validate({"id": "test", "tags": ["regression"], "question": "?", "expect": expect})


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
