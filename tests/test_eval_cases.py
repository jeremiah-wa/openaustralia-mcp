"""The eval case format, as written in evals/cases/*.yaml (see docs/evals.md#cases)."""

from typing import Any

import pytest
from pydantic import ValidationError

from evals.cases import Case, Fixture


def case(**fields: Any) -> Case:
    return Case.model_validate({"id": "test", "tags": ["regression"], "question": "?", "expect": {}} | fields)


class TestFixtures:
    def test_a_bare_name_is_served_for_its_own_request(self) -> None:
        assert case(fixtures=["getRepresentatives_postcode_3056.json"]).fixtures == [
            Fixture(file="getRepresentatives_postcode_3056.json")
        ]

    def test_a_search_fixture_can_list_keywords(self) -> None:
        listed = {"file": "getHansard_search_ndis.json", "search_contains": ["NDIS", "disability"]}

        assert case(fixtures=[listed]).fixtures == [
            Fixture(file="getHansard_search_ndis.json", search_contains=["NDIS", "disability"])
        ]

    def test_names_are_under_the_openaustralia_fixtures(self) -> None:
        assert Fixture(file="getHansard_search_ndis.json").path == "openaustralia/getHansard_search_ndis.json"


class TestDependencies:
    def test_after_must_name_an_expected_call(self) -> None:
        calls = [{"tool": "search_hansard", "after": "member"}]

        with pytest.raises(ValidationError, match="after: no expected call has id 'member'"):
            case(expect={"calls": calls})
