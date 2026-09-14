"""Section schedule: phased development cost, delivery lump sums, and project length."""

import pytest

from core.underwriting.allocation import allocate_lots
from core.underwriting.infrastructure import compute_infrastructure
from core.underwriting.inputs import Costs, DealInputs, LotSize
from core.underwriting.land import compute_land
from core.underwriting.ledger import total
from core.underwriting.lookups import effective_lookups
from core.underwriting.netouts import Acreage, compute_netouts
from core.underwriting.sections import (
    project_length,
    schedule_infrastructure,
    schedule_sections,
)


def test_single_section_phasing() -> None:
    # One lot size, exactly one full section of 36 lots at $10,000 per lot, 10% contingency.
    lots = [
        LotSize(front_footage=50, on=True, yield_per_ac=4, pace=2, wsd_per_ff=120, paving_per_ff=80)
    ]
    costs = Costs(sectional_other_pct=0.10, landscaping_other_pct=0.0)
    allocation = allocate_lots(lots, 9.0)
    sched = schedule_sections(lots, allocation, costs)
    section_cost = 36 * 10_000 * 1.10
    assert sched.total_dev_cost == pytest.approx(section_cost)
    # dev_start_month 1 means the section starts in month 2 and delivers in month 20.
    assert sched.dev_cost[1] == 0.0
    assert sched.dev_cost[2] == pytest.approx(section_cost * 0.10 / 12)
    assert sched.dev_cost[13] == pytest.approx(section_cost * 0.10 / 12)
    assert sched.dev_cost[14] == pytest.approx(section_cost * 0.90 / 6)
    assert sched.dev_cost[19] == pytest.approx(section_cost * 0.90 / 6)
    assert sched.dev_cost[20] == 0.0
    assert total(sched.dev_cost) == pytest.approx(section_cost)
    assert sched.lot_deliveries[20] == 36.0
    assert total(sched.lot_deliveries) == 36.0


def test_delivery_lump_sums() -> None:
    lots = [
        LotSize(
            front_footage=50,
            on=True,
            yield_per_ac=4,
            pace=2,
            landscaping_per_lot=1_000,
            fence_cost_per_ff=90,
            urd_per_lot=40,
            lots_per_streetlight=4,
        )
    ]
    costs = Costs(landscaping_other_pct=0.12, fenced_pct=0.25, cost_per_streetlight=1_700)
    sched = schedule_sections(lots, allocate_lots(lots, 9.0), costs)
    assert sched.landscaping[20] == pytest.approx(36 * 1_000 * 1.12)
    assert sched.fencing[20] == pytest.approx(36 * 90 * 50 * 0.25)
    assert sched.urd[20] == pytest.approx(36 * 40)
    assert sched.streetlights[20] == pytest.approx(36 / 4 * 1_700)
    assert sched.total_fencing == pytest.approx(total(sched.fencing))


def test_cypress_ridge_sections_foot(cypress_main: DealInputs, cypress_acreage: Acreage) -> None:
    costs = cypress_main.costs
    allocation = allocate_lots(costs.lot_sizes, cypress_acreage.residential_developable)
    sched = schedule_sections(costs.lot_sizes, allocation, costs)
    expected = sum(
        lot.total_lots * lot.dev_cost_per_lot * (1 + costs.sectional_other_pct)
        for lot in allocation
        if lot.on
    )
    # Partial sections deliver whole lots, so the schedule foots to lots x cost per lot.
    assert sched.total_dev_cost == pytest.approx(expected)
    assert total(sched.dev_cost) == pytest.approx(sched.total_dev_cost)
    assert total(sched.lot_deliveries) == sum(lot.total_lots for lot in allocation)
    # Four sections per lot size deliver at months 20, 38, 56, 74.
    assert [m for m in range(1, 361) if sched.lot_deliveries[m] > 0] == [20, 38, 56, 74]


def test_infrastructure_ledger_foots(cypress_main: DealInputs, cypress_acreage: Acreage) -> None:
    lookups = effective_lookups(cypress_main.lookups)
    land = compute_land(cypress_main.tract, cypress_main.costs.takedowns)
    infra = compute_infrastructure(cypress_main.tract, cypress_main.costs, lookups, cypress_acreage)
    ledger = schedule_infrastructure(land, infra)
    assert total(ledger.land) == pytest.approx(land.escalated_total)
    assert ledger.land[1] == pytest.approx(land.takedowns[0].total)
    assert ledger.land[37] == pytest.approx(land.takedowns[1].total)
    assert total(ledger.plants) == pytest.approx(infra.total_plants)
    assert total(ledger.amenities) == pytest.approx(infra.total_amenities)
    assert total(ledger.detention) == pytest.approx(infra.total_detention)
    assert total(ledger.other) == pytest.approx(infra.total_other)
    assert total(ledger.roads) == pytest.approx(infra.total_roads)
    assert total(ledger.landscaping) == pytest.approx(
        infra.total_detention_landscaping + infra.total_road_landscaping
    )


def test_project_length_runs_to_last_home_sale(
    cypress_main: DealInputs, cypress_acreage: Acreage
) -> None:
    lookups = effective_lookups(cypress_main.lookups)
    infra = compute_infrastructure(cypress_main.tract, cypress_main.costs, lookups, cypress_acreage)
    allocation = allocate_lots(
        cypress_main.costs.lot_sizes, cypress_acreage.residential_developable
    )
    # Four sections, six-month build, one more section of sales: 2 + 72 + 6 + 18 = 98 months,
    # but the empty fifth road row keeps its default start of month 96 and six-month build.
    assert project_length(infra, cypress_main.costs.lot_sizes, allocation) == 101


def test_project_length_floor_and_empty_road_rows() -> None:
    inputs = DealInputs()
    lookups = effective_lookups(inputs.lookups)
    acreage = compute_netouts(inputs.tract, lookups)
    infra = compute_infrastructure(inputs.tract, inputs.costs, lookups, acreage)
    # Empty road rows keep their default start months and a six-month build, so even an
    # empty tract runs to month 101 (row five starts at month 96), as in the source model.
    assert project_length(infra, [], []) == 101
    # Without road rows the floor of sixty months applies.
    assert project_length(infra.model_copy(update={"roads": []}), [], []) == 60
