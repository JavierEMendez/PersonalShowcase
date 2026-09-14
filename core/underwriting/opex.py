"""Operating costs, development management fee, and project contingency.

Operating windows follow the source model: marketing, marketing personnel, insurance, and
bookkeeping run to the last home sale; professional services, general personnel, and legal run
to the last lot take; MUD and HOA advances run for a share of the delivery window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.underwriting.av import AssessedValue
from core.underwriting.infrastructure import Infrastructure
from core.underwriting.inputs import Costs
from core.underwriting.ledger import MAX_MONTHS, lump, mround, spread, zeros
from core.underwriting.revenue import LotRevenue
from core.underwriting.sections import InfrastructureLedger, SectionSchedule

CONTINGENCY_LAG_MONTHS = 6


@dataclass
class Operating:
    marketing: list[float] = field(default_factory=zeros)
    prof_svc: list[float] = field(default_factory=zeros)
    personnel: list[float] = field(default_factory=zeros)
    marketing_personnel: list[float] = field(default_factory=zeros)
    legal: list[float] = field(default_factory=zeros)
    insurance: list[float] = field(default_factory=zeros)
    bookkeeping: list[float] = field(default_factory=zeros)
    mud_hoa: list[float] = field(default_factory=zeros)
    road_streetlights: list[float] = field(default_factory=zeros)
    last_delivery_month: int = 0
    last_home_month: int = 0
    marketing_total: float = 0.0
    marketing_per_month: float = 0.0
    prof_svc_total: float = 0.0
    prof_svc_per_month: float = 0.0
    personnel_end: int = 0
    marketing_personnel_end: int = 0
    legal_end: int = 0
    insurance_end: int = 0
    bookkeeping_end: int = 0
    mud_end_period: int = 0  # 0-based final period, as the source workbook shows it
    mud_run_months: int = 0
    mud_total: float = 0.0
    road_streetlight_total: float = 0.0


def _run_flat(series: list[float], monthly: float, end_month: int) -> None:
    for month in range(1, end_month + 1):
        if month <= MAX_MONTHS:
            series[month] += monthly


def compute_operating(
    costs: Costs,
    infra: Infrastructure,
    lot_revenue: LotRevenue,
    av: AssessedValue,
    total_revenue_all: float,
    project_months: int,
) -> Operating:
    op = Operating()
    last_lot_rev = max(
        (m for m in range(1, MAX_MONTHS + 1) if lot_revenue.revenue[m] > 0),
        default=project_months,
    )
    op.last_delivery_month = last_lot_rev
    op.last_home_month = av.last_home_sale_month or last_lot_rev

    # Marketing spend equals the marketing fees collected from builders.
    op.marketing_total = lot_revenue.total_marketing_fees
    marketing_months = max(1, op.last_home_month)
    op.marketing_per_month = op.marketing_total / marketing_months
    spread(op.marketing, op.marketing_total, 1, marketing_months)

    # Professional services are a share of all revenue, including pods and bonds.
    op.prof_svc_total = total_revenue_all * costs.prof_svc_pct
    prof_months = max(1, op.last_delivery_month)
    op.prof_svc_per_month = op.prof_svc_total / prof_months
    spread(op.prof_svc, op.prof_svc_total, 1, prof_months)

    op.personnel_end = max(1, op.last_delivery_month)
    _run_flat(op.personnel, costs.personnel_monthly, op.personnel_end)
    op.marketing_personnel_end = max(1, op.last_home_month)
    _run_flat(op.marketing_personnel, costs.marketing_personnel_monthly, op.marketing_personnel_end)
    op.legal_end = max(1, op.last_delivery_month)
    _run_flat(op.legal, costs.legal_monthly, op.legal_end)
    op.insurance_end = max(1, op.last_home_month)
    _run_flat(op.insurance, costs.insurance_monthly, op.insurance_end)
    op.bookkeeping_end = max(1, op.last_home_month)
    _run_flat(op.bookkeeping, costs.bookkeeping_monthly, op.bookkeeping_end)

    # MUD and HOA advances: a share of the delivery window, rounded to whole months.
    if costs.mud_pct > 0:
        op.mud_end_period = int(mround((op.last_delivery_month - 1) * costs.mud_pct, 1))
    op.mud_run_months = max(1, op.mud_end_period + 1)
    _run_flat(op.mud_hoa, costs.mud_monthly, op.mud_run_months)
    op.mud_total = costs.mud_monthly * op.mud_run_months

    # Collector road streetlights land at road delivery.
    for road in infra.roads:
        cost = road.total_lights * costs.cost_per_streetlight if road.total_lights else 0.0
        if cost > 0:
            op.road_streetlight_total += cost
            lump(op.road_streetlights, cost, road.delivery_month)
    return op


def landscaping_all(ledger: InfrastructureLedger, sections: SectionSchedule) -> list[float]:
    series = zeros()
    for month in range(1, MAX_MONTHS + 1):
        series[month] = ledger.landscaping[month] + sections.landscaping[month]
    return series


def compute_dmf(
    costs: Costs,
    ledger: InfrastructureLedger,
    sections: SectionSchedule,
    lot_revenue: LotRevenue,
    op: Operating,
) -> tuple[list[float], float]:
    """Development management fee: a share of each month's hard and soft costs.

    Base: plants, amenities, detention, other, roads, fencing, site work, landscaping, MUD and
    HOA, insurance, legal, lot taxes, professional services, and section development.
    """
    landscaping = landscaping_all(ledger, sections)
    dmf = zeros()
    total = 0.0
    for m in range(1, MAX_MONTHS + 1):
        base = (
            ledger.plants[m]
            + ledger.amenities[m]
            + ledger.detention[m]
            + ledger.other[m]
            + ledger.roads[m]
            + sections.fencing[m]
            + lot_revenue.site_work[m]
            + landscaping[m]
            + op.mud_hoa[m]
            + op.insurance[m]
            + op.legal[m]
            + lot_revenue.taxes[m]
            + op.prof_svc[m]
            + sections.dev_cost[m]
        )
        dmf[m] = base * costs.dmf_pct
        total += dmf[m]
    return dmf, total


def compute_contingency(
    costs: Costs,
    infra: Infrastructure,
    ledger: InfrastructureLedger,
    sections: SectionSchedule,
    lot_revenue: LotRevenue,
    op: Operating,
) -> tuple[list[float], float]:
    """Project contingency on infrastructure and development, spread with a six-month lag.

    Base excludes land, taxes, marketing, mailboxes, brokerage, closing, and operating costs.
    The monthly spread follows the month's infrastructure and development spend.
    """
    base = (
        infra.total_plants
        + infra.total_amenities
        + infra.total_detention
        + sections.total_dev_cost
        + infra.total_other
        + infra.total_roads
        + sections.total_fencing
        + (sections.total_urd + sections.total_streetlights + op.road_streetlight_total)
        + lot_revenue.total_site_work
        + (
            sections.total_landscaping
            + infra.total_detention_landscaping
            + infra.total_road_landscaping
        )
        + op.prof_svc_total
    )
    total = base * costs.contingency

    landscaping = landscaping_all(ledger, sections)
    monthly = zeros()
    for m in range(1, MAX_MONTHS + 1):
        monthly[m] = (
            ledger.plants[m]
            + ledger.amenities[m]
            + ledger.detention[m]
            + ledger.other[m]
            + ledger.roads[m]
            + sections.fencing[m]
            + lot_revenue.site_work[m]
            + landscaping[m]
            + (sections.urd[m] + sections.streetlights[m] + op.road_streetlights[m])
            + lot_revenue.taxes[m]
            + op.prof_svc[m]
            + op.marketing[m]
            + lot_revenue.mailboxes[m]
            + sections.dev_cost[m]
        )
    monthly_total = sum(monthly[1:])

    contingency = zeros()
    for m in range(1, MAX_MONTHS + 1):
        if monthly_total > 0 and monthly[m] > 0:
            share = monthly[m] / monthly_total * total
            lump(contingency, share, m + CONTINGENCY_LAG_MONTHS)
    return contingency, total
