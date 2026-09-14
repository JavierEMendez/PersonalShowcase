"""Lot revenue by take, add-on fees, pods, and the costs booked on the take schedule."""

import pytest

from core.underwriting.allocation import allocate_lots
from core.underwriting.inputs import (
    CommercialPod,
    Costs,
    DealInputs,
    LotSize,
    ResidentialPod,
    Revenue,
    Tract,
)
from core.underwriting.ledger import total
from core.underwriting.netouts import Acreage
from core.underwriting.revenue import (
    compute_lot_revenue,
    compute_pods,
    price_for_month,
    take_schedule,
)


def test_take_schedules() -> None:
    assert take_schedule("50/25/25").pcts == (0.5, 0.25, 0.25, 0.0)
    assert take_schedule("50/25/25").offsets == (0, 6, 9, 9)
    assert take_schedule("25/25/25/25").offsets == (0, 3, 6, 9)
    assert take_schedule("1 Takedown").pcts == (1.0, 0.0, 0.0, 0.0)
    assert take_schedule("50/50").pcts == (0.5, 0.5, 0.0, 0.0)


def test_price_for_month_uses_project_year() -> None:
    prices = [1000.0 + 100 * y for y in range(11)]
    assert price_for_month(prices, 1) == 1000.0
    assert price_for_month(prices, 12) == 1000.0
    assert price_for_month(prices, 13) == 1100.0
    assert price_for_month(prices, 200) == 2000.0  # capped at year 10


def one_section() -> tuple[list[LotSize], Costs, Revenue]:
    lots = [
        LotSize(
            front_footage=50,
            on=True,
            yield_per_ac=4,
            pace=2,
            premium_per_ff=20,
            escalation=0.06,
            fence_per_ff=60,
            marketing_fee=1_000,
            lot_av_pct=0.5,
            lot_tax_rate=0.02,
        )
    ]
    costs = Costs(fenced_pct=0.25, cost_per_mailbox=200, site_work_pct=0.01)
    revenue = Revenue(
        timing_method="50/25/25",
        bem_period=9,
        bem_pct=0.18,
        brokerage_fees=0.03,
        lot_closing_costs=0.015,
        price_per_ff=[2_000.0] * 11,
    )
    return lots, costs, revenue


def test_single_section_lot_revenue() -> None:
    lots, costs, revenue = one_section()
    out = compute_lot_revenue(lots, allocate_lots(lots, 9.0), revenue, costs)
    gross = 36 * 50 * 2_000  # 3,600,000
    # T1 at month 20 (start 2 + 18), BEM nine months earlier, T2 at 26, T3 at 29.
    assert out.revenue[11] == pytest.approx(gross * 0.18)
    remainder = gross * 0.82
    premiums = 36 * 50 * 20
    fence = 36 * 50 * 60 * 0.25
    assert out.revenue[20] == pytest.approx(
        remainder * 0.5 + premiums * 0.5 + fence * 0.5 + 36 * 0.5 * 1_000
    )
    escalation_t2 = 0.06 / 12 * 6 * remainder * 0.25
    assert out.revenue[26] == pytest.approx(
        remainder * 0.25 + premiums * 0.25 + escalation_t2 + fence * 0.25 + 36 * 0.25 * 1_000
    )
    assert out.total_base == pytest.approx(gross)
    assert out.total_premiums == pytest.approx(premiums)
    assert out.total_fence_fees == pytest.approx(fence)
    assert out.total_marketing_fees == pytest.approx(36_000)
    assert out.total_escalation == pytest.approx(
        0.06 / 12 * 6 * remainder * 0.25 + 0.06 / 12 * 9 * remainder * 0.25
    )
    # Costs on gross revenue by take.
    assert total(out.brokerage) == pytest.approx(gross * 0.03)
    assert total(out.closing) == pytest.approx(gross * 0.015)
    assert total(out.mailboxes) == pytest.approx(36 * 200)
    assert total(out.taxes) == pytest.approx(36 * 2_000 * 50 * 0.5 * 0.02)
    assert out.brokerage[20] == pytest.approx(gross * 0.5 * 0.03)
    # Site work with the earnest money.
    assert out.site_work[11] == pytest.approx(gross * 0.01)
    assert out.total_site_work == pytest.approx(gross * 0.01)


def test_cypress_ridge_lot_revenue_foots(
    cypress_main: DealInputs, cypress_acreage: Acreage
) -> None:
    costs, revenue = cypress_main.costs, cypress_main.revenue
    allocation = allocate_lots(costs.lot_sizes, cypress_acreage.residential_developable)
    out = compute_lot_revenue(costs.lot_sizes, allocation, revenue, costs)
    gross = sum(lot.total_lots * lot.front_footage * 1_800 for lot in allocation if lot.on)
    assert out.total_base == pytest.approx(gross)
    assert total(out.revenue) == pytest.approx(
        out.total_base
        + out.total_premiums
        + out.total_escalation
        + out.total_fence_fees
        + out.total_marketing_fees
    )
    assert total(out.brokerage) == pytest.approx(gross * revenue.brokerage_fees)


def test_pods_split_acres_across_priced_pods() -> None:
    tract = Tract(commercial_pod_acres=22.0, residential_pod_acres=12.0)
    revenue = Revenue(
        res_pods=[
            ResidentialPod(
                price_per_acre=350_000,
                closing_costs_pct=0.045,
                implied_lots_per_acre=3.5,
                impact_fee_per_lot=10_000,
                sale_period=12,
            )
        ],
        comm_pods=[
            CommercialPod(price_per_sf=8, sale_period=12),
            CommercialPod(price_per_sf=8, sale_period=36),
        ],
    )
    pods = compute_pods(tract, revenue, project_months=100)
    assert pods.acres_per_residential_pod == 12.0
    assert pods.acres_per_commercial_pod == 11.0
    res = 12 * 350_000 * 0.955 + 10_000 * 3.5 * 12
    assert pods.residential[12] == pytest.approx(res)
    assert pods.total_residential == pytest.approx(res)
    comm_each = 11 * 43_560 * 8 * 0.955
    assert pods.commercial[12] == pytest.approx(comm_each)
    assert pods.commercial[36] == pytest.approx(comm_each)
    assert pods.total_commercial == pytest.approx(2 * comm_each)


def test_unpriced_pods_default_sale_to_project_end() -> None:
    tract = Tract(commercial_pod_acres=10.0)
    revenue = Revenue(comm_pods=[CommercialPod(price_per_sf=5)])
    pods = compute_pods(tract, revenue, project_months=80)
    assert pods.commercial[80] == pytest.approx(10 * 43_560 * 5 * 0.955)
