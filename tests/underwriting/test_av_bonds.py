"""Assessed value buildup and district bond reimbursements."""

import pytest

from core.underwriting.allocation import allocate_lots
from core.underwriting.av import compute_av
from core.underwriting.bonds import compute_bond
from core.underwriting.inputs import Bond, CommercialPod, LotSize, Revenue, Tract
from core.underwriting.ledger import zeros
from core.underwriting.revenue import PodRevenue, compute_pods


def test_homes_complete_after_build_time_and_sell_at_pace() -> None:
    lots = [
        LotSize(
            front_footage=50,
            on=True,
            yield_per_ac=4,
            pace=2,
            build_time=6,
            home_price=400_000,
            av_pct=0.85,
        )
    ]
    revenue = Revenue(timing_method="1 Takedown")
    av = compute_av(lots, allocate_lots(lots, 9.0), revenue, PodRevenue(), project_months=80)
    # 36 lots deliver at month 20; homes complete at month 26; sales start the month after,
    # two per month for 18 months.
    assert av.home_sales[26] == 0.0
    assert av.home_sales[27] == 2.0
    assert av.home_sales[44] == 2.0
    assert av.home_sales[45] == 0.0
    assert av.last_home_sale_month == 44
    assert av.av_by_month[27] == pytest.approx(2 * 400_000 * 0.85)
    assert av.lot_av == pytest.approx(36 * 400_000 * 0.85)
    assert av.cumulative[44] == pytest.approx(av.lot_av)


def test_commercial_av_lands_after_delay() -> None:
    tract = Tract(commercial_pod_acres=10.0)
    revenue = Revenue(
        comm_pods=[
            CommercialPod(price_per_sf=8, sale_period=12, av_per_acre=1_000_000, av_delay_months=18)
        ]
    )
    pods = compute_pods(tract, revenue, project_months=80)
    av = compute_av([], [], revenue, pods, project_months=80)
    assert av.commercial_av == pytest.approx(10_000_000)
    assert av.av_by_month[30] == pytest.approx(10_000_000)
    assert av.cumulative[29] == 0.0
    assert av.cumulative[30] == pytest.approx(10_000_000)


def test_bond_issuances_follow_lagged_cumulative_av() -> None:
    cumulative = zeros()
    # AV grows 1,000,000 per month from month 1.
    for m in range(1, 361):
        cumulative[m] = 1_000_000.0 * m
    bond = Bond(
        debt_ratio=0.10,
        first_bond_period=24,
        bond_interval=12,
        pct_to_dev=0.85,
        receivables_fee=0.02,
    )
    out = compute_bond(bond, cumulative)
    # First issuance at month 24 on AV as of month 21.
    first_month, first_amount = out.issuances[0]
    assert first_month == 24
    assert first_amount == pytest.approx(21_000_000 * 0.10 * 0.85)
    # Next issuance covers the twelve months of new AV.
    second_month, second_amount = out.issuances[1]
    assert second_month == 36
    assert second_amount == pytest.approx(12_000_000 * 0.10 * 0.85)
    assert out.revenue[24] == pytest.approx(21_000_000 * 0.10 * 0.85)
    assert out.fees[24] == pytest.approx(out.revenue[24] * 0.02)
    assert out.total == pytest.approx(sum(a for _, a in out.issuances))
    assert out.total_fees == pytest.approx(out.total * 0.02)


def test_bond_off_or_unscheduled_pays_nothing() -> None:
    cumulative = [1_000_000.0] * 361
    assert compute_bond(Bond(toggle=False, first_bond_period=12), cumulative).issuances == []
    assert compute_bond(Bond(first_bond_period=0), cumulative).issuances == []
    assert compute_bond(Bond(debt_ratio=0.0, first_bond_period=12), cumulative).issuances == []
