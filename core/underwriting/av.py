"""Assessed value buildup: lots deliver in takes, homes complete after the build time, and sell
from completed inventory at the sales pace. Cumulative AV drives the district bonds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.underwriting.allocation import SECTION_MONTHS, LotAllocation, section_lots
from core.underwriting.inputs import LotSize, Revenue
from core.underwriting.ledger import MAX_MONTHS, in_range, lump, zeros
from core.underwriting.revenue import PodRevenue, take_schedule


@dataclass
class AssessedValue:
    av_by_month: list[float] = field(default_factory=zeros)
    home_sales: list[float] = field(default_factory=zeros)
    cumulative: list[float] = field(default_factory=zeros)
    lot_av: float = 0.0
    commercial_av: float = 0.0
    last_home_sale_month: int = 0


def compute_av(
    lot_sizes: list[LotSize],
    allocation: list[LotAllocation],
    revenue: Revenue,
    pods: PodRevenue,
    project_months: int,
) -> AssessedValue:
    takes = take_schedule(revenue.timing_method)
    out = AssessedValue()

    for ls, lot in zip(lot_sizes, allocation, strict=True):
        if not lot.on or lot.total_lots == 0 or lot.pace <= 0:
            continue
        start_month = ls.dev_start_month + 1
        build_time = max(0, ls.build_time)
        av_per_lot = ls.home_price * ls.av_pct
        if av_per_lot <= 0:
            continue

        # Homes complete `build_time` months after each take of each section.
        completions = zeros()
        for k, lots in section_lots(lot):
            delivery = start_month + k * SECTION_MONTHS
            for offset, frac in zip(takes.offsets, takes.pcts, strict=True):
                if frac > 0:
                    lump(completions, lots * frac, delivery + offset + build_time)

        # Sales are limited by pace and by the prior month's ending inventory.
        cum_completed = 0.0
        cum_sold = 0.0
        prev_inventory = 0.0
        for month in range(1, MAX_MONTHS + 1):
            sold = min(prev_inventory, lot.pace)
            cum_sold += sold
            out.av_by_month[month] += sold * av_per_lot
            out.home_sales[month] += sold
            if sold > 0:
                # Overwritten by each lot size in turn, so this is the last sale month of the
                # last lot size processed, as in the source model.
                out.last_home_sale_month = month
            cum_completed += completions[month]
            prev_inventory = cum_completed - cum_sold

    out.lot_av = sum(out.av_by_month[1:])

    # Commercial AV lands a fixed delay after each pod sale.
    for i, pod in enumerate(revenue.comm_pods):
        if i >= pods.commercial_pod_count:
            break
        sale_month = project_months if pod.sale_period is None else pod.sale_period
        pod_av = pods.acres_per_commercial_pod * pod.av_per_acre
        out.commercial_av += pod_av
        av_month = sale_month + pod.av_delay_months
        if pod_av > 0 and in_range(av_month):
            out.av_by_month[av_month] += pod_av

    for month in range(1, MAX_MONTHS + 1):
        out.cumulative[month] = out.cumulative[month - 1] + out.av_by_month[month]
    return out
