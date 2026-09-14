"""Revenue: lot takedowns with builder earnest money, add-on fees, and pod sales.

Each section delivers all of its lots at T1. Builder earnest money (BEM) arrives `bem_period`
months before T1; the remainder is split across takes T1..T4 by the timing method. Premiums,
fence fees, and marketing fees follow the take weights. Escalation accrues from T1 to each
later take. Brokerage, lot closing costs, lot taxes, and mailboxes are booked as costs on the
same schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.underwriting.allocation import SECTION_MONTHS, LotAllocation, section_lots
from core.underwriting.inputs import (
    CommercialPod,
    Costs,
    LotSize,
    ResidentialPod,
    Revenue,
    TimingMethod,
    Tract,
)
from core.underwriting.ledger import in_range, lump, zeros
from core.underwriting.netouts import SF_PER_ACRE


@dataclass(frozen=True)
class TakeSchedule:
    pcts: tuple[float, float, float, float]
    offsets: tuple[int, int, int, int]  # months after T1 for T1..T4


def take_schedule(method: TimingMethod) -> TakeSchedule:
    if method == "25/25/25/25":
        return TakeSchedule((0.25, 0.25, 0.25, 0.25), (0, 3, 6, 9))
    if method == "1 Takedown":
        return TakeSchedule((1.0, 0.0, 0.0, 0.0), (0, 6, 9, 9))
    if method == "50/50":
        return TakeSchedule((0.5, 0.5, 0.0, 0.0), (0, 6, 9, 9))
    return TakeSchedule((0.5, 0.25, 0.25, 0.0), (0, 6, 9, 9))


def price_for_month(price_per_ff: list[float], t1: int) -> float:
    """Lot price per front foot for the project year that contains T1 (year 0 is months 1-12)."""
    year_idx = min(max(int((t1 - 1) / 12), 0), 10)
    return price_per_ff[year_idx] if year_idx < len(price_per_ff) else price_per_ff[-1]


@dataclass
class LotRevenue:
    revenue: list[float] = field(default_factory=zeros)
    brokerage: list[float] = field(default_factory=zeros)
    closing: list[float] = field(default_factory=zeros)
    taxes: list[float] = field(default_factory=zeros)
    mailboxes: list[float] = field(default_factory=zeros)
    site_work: list[float] = field(default_factory=zeros)
    total_base: float = 0.0
    total_premiums: float = 0.0
    total_escalation: float = 0.0
    total_fence_fees: float = 0.0
    total_marketing_fees: float = 0.0
    total_site_work: float = 0.0


def compute_lot_revenue(
    lot_sizes: list[LotSize], allocation: list[LotAllocation], revenue: Revenue, costs: Costs
) -> LotRevenue:
    takes = take_schedule(revenue.timing_method)
    out = LotRevenue()
    for ls, lot in zip(lot_sizes, allocation, strict=True):
        if not lot.on or lot.total_lots == 0 or lot.pace <= 0:
            continue
        start_month = ls.dev_start_month + 1
        ff = ls.front_footage
        # Lot taxes use the year-0 price, not the delivery-year price.
        lot_tax_per_lot = revenue.price_per_ff[0] * ff * ls.lot_av_pct * ls.lot_tax_rate

        for k, batch in section_lots(lot):
            t1 = start_month + k * SECTION_MONTHS
            months = [t1 + offset for offset in takes.offsets]
            ff_rate = price_for_month(revenue.price_per_ff, t1)
            gross = batch * ff * ff_rate

            # Builder earnest money ahead of the first take.
            bem_amount = gross * revenue.bem_pct
            bem_month = max(1, t1 - revenue.bem_period)
            if in_range(bem_month):
                out.revenue[bem_month] += bem_amount
                out.total_base += bem_amount

            # Remaining lot revenue by take.
            remainder = gross * (1 - revenue.bem_pct)
            for month, pct in zip(months, takes.pcts, strict=True):
                if pct > 0 and in_range(month):
                    out.revenue[month] += remainder * pct
                    out.total_base += remainder * pct

            # Costs on the take schedule, on gross revenue before BEM.
            for month, pct in zip(months, takes.pcts, strict=True):
                if pct <= 0 or not in_range(month):
                    continue
                if revenue.brokerage_fees:
                    out.brokerage[month] += gross * pct * revenue.brokerage_fees
                if revenue.lot_closing_costs:
                    out.closing[month] += gross * pct * revenue.lot_closing_costs
                if lot_tax_per_lot:
                    out.taxes[month] += batch * pct * lot_tax_per_lot
                if costs.cost_per_mailbox:
                    out.mailboxes[month] += batch * pct * costs.cost_per_mailbox

            # Premiums
            if ls.premium_per_ff and ff:
                premium_total = batch * ff * ls.premium_per_ff
                for month, pct in zip(months, takes.pcts, strict=True):
                    if pct > 0 and in_range(month):
                        out.revenue[month] += premium_total * pct
                        out.total_premiums += premium_total * pct

            # Escalation on later takes: annual rate, prorated by months since T1.
            if ls.escalation:
                for month, pct in list(zip(months, takes.pcts, strict=True))[1:]:
                    amount = (ls.escalation / 12) * (month - t1) * (remainder * pct)
                    if amount > 0 and in_range(month):
                        out.revenue[month] += amount
                        out.total_escalation += amount

            # Fence fees on the fenced share of lots.
            if ls.fence_per_ff and ff and costs.fenced_pct:
                fence_total = batch * ff * ls.fence_per_ff * costs.fenced_pct
                for month, pct in zip(months, takes.pcts, strict=True):
                    if pct > 0 and in_range(month):
                        out.revenue[month] += fence_total * pct
                        out.total_fence_fees += fence_total * pct

            # Marketing fees per lot.
            if ls.marketing_fee:
                for month, pct in zip(months, takes.pcts, strict=True):
                    if pct > 0 and in_range(month):
                        out.revenue[month] += batch * pct * ls.marketing_fee
                        out.total_marketing_fees += batch * pct * ls.marketing_fee

            # Site work is a cost booked with the earnest money, as a share of gross revenue.
            site_work = gross * costs.site_work_pct
            out.total_site_work += site_work
            lump(out.site_work, site_work, bem_month)
    return out


def pod_count(pods: list[ResidentialPod] | list[CommercialPod]) -> int:
    """Number of priced pods sharing the pod acreage, at least one."""
    priced = 0
    for pod in pods:
        price = pod.price_per_acre if isinstance(pod, ResidentialPod) else pod.price_per_sf
        if price:
            priced += 1
    return max(priced or 1, 1)


@dataclass
class PodRevenue:
    residential: list[float] = field(default_factory=zeros)
    commercial: list[float] = field(default_factory=zeros)
    total_residential: float = 0.0
    total_commercial: float = 0.0
    acres_per_residential_pod: float = 0.0
    acres_per_commercial_pod: float = 0.0
    commercial_pod_count: int = 1


def compute_pods(tract: Tract, revenue: Revenue, project_months: int) -> PodRevenue:
    out = PodRevenue()
    res_count = pod_count(revenue.res_pods)
    out.acres_per_residential_pod = tract.residential_pod_acres / res_count
    for i, pod in enumerate(revenue.res_pods):
        if i >= res_count:
            break
        sale_month = project_months if pod.sale_period is None else pod.sale_period
        acres = out.acres_per_residential_pod
        # Land price net of closing costs plus impact fees on the implied lot count.
        pod_rev = (
            acres * pod.price_per_acre * (1 - pod.closing_costs_pct)
            + pod.impact_fee_per_lot * pod.implied_lots_per_acre * acres
        )
        out.total_residential += pod_rev
        if pod_rev > 0:
            lump(out.residential, pod_rev, sale_month)

    comm_count = pod_count(revenue.comm_pods)
    out.commercial_pod_count = comm_count
    out.acres_per_commercial_pod = tract.commercial_pod_acres / comm_count
    for i, cpod in enumerate(revenue.comm_pods):
        if i >= comm_count:
            break
        sale_month = project_months if cpod.sale_period is None else cpod.sale_period
        pod_rev = (
            out.acres_per_commercial_pod
            * SF_PER_ACRE
            * cpod.price_per_sf
            * (1 - cpod.closing_costs_pct)
        )
        out.total_commercial += pod_rev
        if pod_rev > 0:
            lump(out.commercial, pod_rev, sale_month)
    return out
