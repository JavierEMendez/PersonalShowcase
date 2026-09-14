"""The engine reproduces the Cypress Ridge reference fixture to the dollar, and its tables foot.

The fixture in tests/fixtures/cypress_ridge.json was produced by this engine and reconciled
line by line against the internal underwriting tool it was ported from. Any change to the
model that moves a figure fails here.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from core.underwriting.engine import run
from core.underwriting.inputs import DealInputs
from core.underwriting.summary import Outputs
from tests.underwriting.conftest import load_scenario

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cypress_ridge.json"


@pytest.fixture(scope="module")
def main_outputs(cypress_main: DealInputs) -> Outputs:
    return run(cypress_main)


@pytest.fixture(scope="module")
def fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def assert_matches(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert actual.keys() == expected.keys(), path
        for key in expected:
            assert_matches(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            assert_matches(a, e, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=1e-6), path
    else:
        assert actual == expected, path


def test_main_scenario_matches_fixture(main_outputs: Outputs, fixture: dict[str, Any]) -> None:
    assert_matches(main_outputs.model_dump(mode="json"), fixture, "outputs")


def test_tables_foot(main_outputs: Outputs) -> None:
    out = main_outputs
    rev = out.revenue.model_dump()
    assert rev["total"] == sum(v for k, v in rev.items() if k != "total")
    cost = out.costs.model_dump()
    assert cost["total"] == sum(v for k, v in cost.items() if k != "total")
    btl = out.below_line.model_dump()
    assert btl["total"] == sum(v for k, v in btl.items() if k != "total")
    assert out.summary.gross_margin == out.revenue.total - out.costs.total
    assert out.summary.net_margin == out.summary.gross_margin - out.below_line.total
    assert out.summary.total_cost == out.costs.total + out.below_line.total
    # Yearly cumulative is the running sum of the rounded nets.
    running = 0
    for row in out.yearly:
        running += row.net
        assert row.cumulative == running
    assert out.yearly[-1].cumulative == pytest.approx(out.summary.net_margin, abs=len(out.yearly))
    # Monthly rows sum to the yearly rows within rounding.
    for row in out.yearly:
        months = [m for m in out.cf_monthly if m.year == row.year]
        assert sum(m.net for m in months) == pytest.approx(row.net, abs=len(months))
    # Waterfall foots to gross margin.
    wf = out.waterfall
    assert (
        wf.revenues + wf.land + wf.sections + wf.infrastructure + wf.amenities + wf.other
        == wf.gross_margin
    )


def test_headline_figures(main_outputs: Outputs) -> None:
    s = main_outputs.summary
    assert s.total_lots == 2380
    assert s.project_length_months == 101
    assert s.unlevered_irr is not None
    assert 0.17 < s.unlevered_irr < 0.18
    assert 0.22 < s.gross_margin_of_revenue < 0.24
    assert s.breakeven_year == 6
    assert s.peak_cash_month == 37


def test_scenarios_move_in_the_expected_direction(main_outputs: Outputs) -> None:
    faster = run(load_scenario("Faster pace")).summary
    lower = run(load_scenario("Lower lot price")).summary
    base = main_outputs.summary
    assert base.unlevered_irr is not None
    assert faster.unlevered_irr is not None and faster.unlevered_irr > base.unlevered_irr
    assert lower.unlevered_irr is not None and lower.unlevered_irr < base.unlevered_irr
    assert lower.total_revenue < base.total_revenue
    assert faster.total_lots == base.total_lots
