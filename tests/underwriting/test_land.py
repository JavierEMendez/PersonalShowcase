"""Land takedowns escalate the purchase price and never the closing costs."""

import pytest

from core.underwriting.inputs import DealInputs, Takedown, Tract
from core.underwriting.land import compute_land


def test_cypress_ridge_takedowns(cypress_main: DealInputs) -> None:
    land = compute_land(cypress_main.tract, cypress_main.costs.takedowns)
    assert land.purchase_price == pytest.approx(28_800_000)
    assert land.closing_costs == pytest.approx(1_296_000)
    assert len(land.takedowns) == 2
    first, second = land.takedowns
    assert first.period == 0
    assert first.purchase_price == pytest.approx(14_400_000)
    assert first.closing_costs == pytest.approx(648_000)
    # Second take at month 36 escalates three years at 5%.
    assert second.purchase_price == pytest.approx(14_400_000 * 1.05**3)
    assert second.closing_costs == pytest.approx(648_000)
    assert land.escalated_total == pytest.approx(first.total + second.total)
    assert land.takedown_pct_check == 1.0


def test_missing_takedowns_default_to_one_take_at_close() -> None:
    tract = Tract(gross_acreage=100, purchase_price_per_acre=10_000, closing_costs_pct=0.04)
    land = compute_land(tract, [Takedown(period=12, pct=0.0)])
    assert len(land.takedowns) == 1
    assert land.takedowns[0].period == 0
    assert land.takedowns[0].total == pytest.approx(1_040_000)
