"""Lot allocation splits residential acres by 18-month consumption."""

import pytest

from core.underwriting.allocation import allocate_lots, section_lots
from core.underwriting.inputs import DealInputs, LotSize
from core.underwriting.netouts import Acreage


def test_cypress_ridge_allocation(cypress_main: DealInputs, cypress_acreage: Acreage) -> None:
    rows = allocate_lots(cypress_main.costs.lot_sizes, cypress_acreage.residential_developable)
    active = [r for r in rows if r.on]
    assert [r.front_footage for r in active] == [40, 45, 50, 60, 80]
    # Same pace and yield on every size, so every size takes one fifth of the acres.
    for r in active:
        assert r.lots_18mo == 126.0
        assert r.acres_18mo == pytest.approx(126 / 5.5)
        assert r.allocated_acres == pytest.approx(cypress_acreage.residential_developable / 5)
        assert r.full_sections == 3
        assert r.last_lots == 98
        assert r.total_lots == 476
        assert [k for k, _ in section_lots(r)] == [1, 2, 3, 4]
        assert section_lots(r)[-1] == (4, 98.0)
    assert sum(r.total_lots for r in rows) == 2380
    assert rows[0].on is False and rows[0].total_lots == 0
    assert active[2].dev_cost_per_lot == pytest.approx((580 + 440) * 50)


def test_partial_section_is_dropped_when_it_rounds_to_zero_lots() -> None:
    lots = [LotSize(front_footage=50, on=True, yield_per_ac=4, pace=2)]
    # 36 lots per section on 9 acres; allocate exactly two sections plus a sliver.
    rows = allocate_lots(lots, 18.1)
    assert rows[0].full_sections == 2
    assert rows[0].last_lots == 0
    assert rows[0].total_lots == 72
    assert section_lots(rows[0]) == [(1, 36.0), (2, 36.0)]
