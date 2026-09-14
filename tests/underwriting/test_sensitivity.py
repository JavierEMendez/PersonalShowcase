"""Sensitivity grid: axis scaling, labels, heat ranking, and the base-case cell."""

import pytest

from core.underwriting.engine import run
from core.underwriting.inputs import DealInputs
from core.underwriting.sensitivity import axis_label, build_grid, scale_axis


def test_scale_axis_touches_only_its_driver(cypress_main: DealInputs) -> None:
    scaled = scale_axis(cypress_main, "lot_price", 1.05)
    assert scaled.revenue.price_per_ff[0] == pytest.approx(1890)
    assert scaled.costs.lot_sizes == cypress_main.costs.lot_sizes
    paced = scale_axis(cypress_main, "pace", 1.2)
    active = [ls for ls in paced.costs.lot_sizes if ls.on]
    assert all(ls.pace == pytest.approx(8.4) for ls in active)
    assert all(ls.pace == 0.0 for ls in paced.costs.lot_sizes if not ls.on)
    assert paced.revenue.price_per_ff == cypress_main.revenue.price_per_ff


def test_axis_labels(cypress_main: DealInputs) -> None:
    assert axis_label(cypress_main, "lot_price", 0.95) == "$1,710"
    assert axis_label(cypress_main, "pace", 1.1) == "7.7"
    assert axis_label(cypress_main, "yield", 1.0) == "5.50"
    assert axis_label(cypress_main, "contingency", 1.1) == "5.5%"
    assert axis_label(cypress_main, "home_price", 1.05) == "+5%"
    assert axis_label(cypress_main, "dev_cost", 1.0) == "Base"


def test_default_grid_matches_engine_and_marks_base(cypress_main: DealInputs) -> None:
    grid = build_grid(cypress_main)
    assert grid.col_labels == ["$1,620", "$1,710", "$1,800", "$1,890", "$1,980"]
    assert [r.label for r in grid.rows] == ["8.4", "7.7", "7.0", "6.3", "5.6"]
    base_cells = [(i, j) for i, r in enumerate(grid.rows) for j, c in enumerate(r.cells) if c.base]
    assert base_cells == [(2, 2)]
    centre = grid.rows[2].cells[2].value
    assert centre == pytest.approx(run(cypress_main).summary.unlevered_irr)
    # Higher price and faster pace both raise the IRR, so the top-right cell is the hottest.
    assert grid.rows[0].cells[-1].heat == 9
    assert grid.rows[-1].cells[0].heat == 1
    values = [c.value for r in grid.rows for c in r.cells]
    assert all(v is not None for v in values)
    for row in grid.rows:
        cells = [c.value for c in row.cells if c.value is not None]
        assert cells == sorted(cells)


def test_grid_size_is_clamped(cypress_main: DealInputs) -> None:
    grid = build_grid(cypress_main, row_steps=5, col_steps=1, metric="gross_margin")
    assert len(grid.rows) == 7
    assert len(grid.rows[0].cells) == 3
    assert grid.rows[3].cells[1].base is True
