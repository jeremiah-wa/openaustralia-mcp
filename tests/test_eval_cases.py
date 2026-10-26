"""The eval case format, as written in evals/cases/*.yaml (see docs/evals.md#cases)."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evals.cases import Case, Fixture

from .fake_api import RECORDED

CASES = sorted((Path(__file__).parent.parent / "evals" / "cases").glob("*.yaml"))


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

    def test_any_parameter_can_list_texts_its_value_is_part_of(self) -> None:
        listed = {"file": "getSenators_party_Greens.json", "part_of": {"party": ["Australian Greens"]}}

        [fixture] = case(fixtures=[listed]).fixtures

        assert fixture.part_of == {"party": ["Australian Greens"]}

    def test_names_are_under_the_openaustralia_fixtures(self) -> None:
        assert Fixture(file="getHansard_search_ndis.json").path == "openaustralia/getHansard_search_ndis.json"


class TestDependencies:
    def test_after_must_name_an_expected_call(self) -> None:
        calls = [{"tool": "search_hansard", "after": "member"}]

        with pytest.raises(ValidationError, match="after: no expected call has id 'member'"):
            case(expect={"calls": calls})


class TestCommittedCases:
    """The case files themselves. A fixture missing from RECORDED would otherwise only show up as a run error."""

    @pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
    def test_loads_and_names_only_recorded_fixtures(self, path: Path) -> None:
        yaml = pytest.importorskip("yaml")

        committed = Case.model_validate(yaml.safe_load(path.read_text("utf-8")))

        assert committed.id == path.stem
        assert [fixture.path for fixture in committed.fixtures if fixture.path not in RECORDED] == []
