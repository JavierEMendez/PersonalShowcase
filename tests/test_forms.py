"""Posted input forms merge into typed inputs with the documented semantics."""

import pytest
from pydantic import ValidationError

from app import forms
from core.underwriting.inputs import DealInputs
from tests.underwriting.conftest import load_scenario


@pytest.fixture
def main() -> DealInputs:
    return load_scenario("Main")


def test_percent_fields_are_stored_as_fractions(main: DealInputs) -> None:
    updated = forms.apply_form(main, {"tract.closing_costs_pct": "5", "costs.contingency": "7.5"})
    assert updated.tract.closing_costs_pct == pytest.approx(0.05)
    assert updated.costs.contingency == pytest.approx(0.075)
    # Untouched values survive.
    assert updated.tract.gross_acreage == main.tract.gross_acreage


def test_numbers_accept_separators_and_symbols(main: DealInputs) -> None:
    updated = forms.apply_form(main, {"tract.purchase_price_per_acre": "$47,500"})
    assert updated.tract.purchase_price_per_acre == 47_500


def test_blank_resets_to_default_and_missing_keeps_value(main: DealInputs) -> None:
    assert main.costs.personnel_monthly == 50_000
    updated = forms.apply_form(main, {"costs.personnel_monthly": ""})
    assert updated.costs.personnel_monthly == 0.0  # model default
    assert updated.costs.legal_monthly == main.costs.legal_monthly


def test_list_rows_merge_by_index(main: DealInputs) -> None:
    # The Revenue tab edits home fields; Costs-tab fields on the same row must survive.
    updated = forms.apply_form(main, {"costs.lot_sizes.3.home_price": "300000"})
    assert updated.costs.lot_sizes[3].home_price == 300_000
    assert updated.costs.lot_sizes[3].pace == main.costs.lot_sizes[3].pace
    assert updated.costs.lot_sizes[3].on is True
    assert len(updated.costs.lot_sizes) == 16


def test_checkboxes_off_when_absent_from_named_paths(main: DealInputs) -> None:
    paths = [f"costs.lot_sizes.{i}.on" for i in range(16)]
    updated = forms.apply_form(main, {"costs.lot_sizes.3.on": "on"}, paths)
    assert [ls.on for ls in updated.costs.lot_sizes].count(True) == 1
    assert updated.costs.lot_sizes[3].on is True


def test_new_list_rows_are_appended(main: DealInputs) -> None:
    assert len(main.tract.plants) == 3
    updated = forms.apply_form(main, {"tract.plants.5.type": "Lift Station"})
    assert len(updated.tract.plants) == 6
    assert updated.tract.plants[5].type == "Lift Station"
    assert updated.tract.plants[3].type == "None"


def test_lookup_overrides_keyed_by_type_name(main: DealInputs) -> None:
    updated = forms.apply_form(
        main, {"lookups.plants.Water Plant.acres": "4", "lookups.plants.Water Plant.duration": "9"}
    )
    assert updated.lookups.plants["Water Plant"].acres == 4
    assert updated.lookups.plants["Water Plant"].duration == 9


def test_bad_number_raises(main: DealInputs) -> None:
    with pytest.raises(ValueError):
        forms.apply_form(main, {"revenue.price_per_ff.0": "abc"})


def test_invalid_choice_raises_validation_error(main: DealInputs) -> None:
    with pytest.raises(ValidationError) as exc:
        forms.apply_form(main, {"tract.plants.0.type": "Reactor"})
    assert forms.validation_messages(exc.value)
