"""Summary outputs: revenue and cost lines, margins, per-acre and per-lot metrics, cash flow
tables by month, quarter, and year.

Every displayed line is rounded to the dollar and the totals are recomputed from the rounded
lines, so the tables foot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import BaseModel

from core.underwriting.allocation import LotAllocation
from core.underwriting.av import AssessedValue
from core.underwriting.bonds import BondProceeds
from core.underwriting.infrastructure import Infrastructure
from core.underwriting.inputs import Costs, DealInputs
from core.underwriting.irr import cashflow_dates, monthly_irr, xirr
from core.underwriting.land import Land
from core.underwriting.ledger import MAX_MONTHS
from core.underwriting.netouts import Acreage
from core.underwriting.opex import Operating
from core.underwriting.revenue import LotRevenue, PodRevenue
from core.underwriting.sections import InfrastructureLedger, SectionSchedule


class RevenueLines(BaseModel):
    lot_sales: int
    mud: int
    wcid: int
    premiums: int
    fence_fees: int
    escalations: int
    marketing_fees: int
    residential_pods: int
    commercial_pods: int
    total: int


class CostLines(BaseModel):
    land: int
    plants: int
    amenities: int
    detention: int
    sections: int
    other: int
    roads: int
    fencing: int
    dry_utilities: int
    site_work: int
    landscaping: int
    legal: int
    lot_taxes: int
    mud_hoa: int
    insurance: int
    marketing: int
    brokerage: int
    closing: int
    mailboxes: int
    professional_services: int
    contingency: int
    total: int


class BelowTheLine(BaseModel):
    dmf: int
    personnel: int
    bookkeeping: int
    receivables_fees: int
    total: int


class OperatingDetail(BaseModel):
    """Operating cost windows. Final periods are 0-based, as the source workbook shows them."""

    marketing_total: int
    marketing_per_month: int
    marketing_final_period: int
    prof_services_total: int
    prof_services_per_month: int
    prof_services_final_period: int
    general_personnel_total: int
    general_final_period: int
    marketing_personnel_total: int
    marketing_personnel_final_period: int
    legal_total: int
    legal_final_period: int
    mud_hoa_total: int
    mud_hoa_monthly: int
    mud_hoa_final_period: int
    insurance_total: int
    insurance_final_period: int
    bookkeeping_total: int
    bookkeeping_final_period: int
    dmf_total: int


class Summary(BaseModel):
    unlevered_irr: float | None
    total_revenue: int
    gross_costs: int
    gross_margin: int
    gross_margin_of_revenue: float
    gross_margin_of_costs: float
    below_line_total: int
    total_cost: int
    net_margin: int
    net_margin_of_revenue: float
    net_margin_of_costs: float
    return_on_cost: float
    total_lots: int
    lot_supply_18mo: int
    home_sales_per_year: int
    project_length_months: int
    project_length_years: float
    developable_acres: float
    residential_developable_acres: float
    rev_per_dev_acre: int
    cost_per_dev_acre: int
    infra_per_dev_acre: int
    gm_per_acre: int
    infra_per_lot: int
    amenities_per_lot: int
    lot_av: int
    comm_av: int
    peak_cash_need: int
    peak_cash_month: int
    breakeven_month: int | None
    breakeven_year: int | None


class Waterfall(BaseModel):
    revenues: int
    land: int
    sections: int
    infrastructure: int
    amenities: int
    other: int
    gross_margin: int


class MonthlyCashflow(BaseModel):
    month: int
    year: int
    revenue: int
    cost: int
    net: int
    rev_lot_sales: int
    rev_res_pods: int
    rev_comm_pods: int
    rev_mud_wcid: int
    cost_land: int
    cost_plants: int
    cost_amenities: int
    cost_detention: int
    cost_other: int
    cost_roads: int
    cost_sections: int
    cost_landscaping: int
    cost_fencing: int
    cost_dry_utilities: int
    cost_site_work: int
    cost_dmf: int
    cost_operating: int


class QuarterlyCashflow(BaseModel):
    quarter: int
    year: int
    quarter_of_year: int
    revenue: int
    cost: int
    net: int


class YearlyRow(BaseModel):
    year: int
    revenue: int
    cost: int
    net: int
    cumulative: int
    lots: int
    homes: int


class Outputs(BaseModel):
    acreage: Acreage
    land: Land
    infrastructure: Infrastructure
    lots: list[LotAllocation]
    revenue: RevenueLines
    costs: CostLines
    below_line: BelowTheLine
    operating: OperatingDetail
    summary: Summary
    waterfall: Waterfall
    yearly: list[YearlyRow]
    cf_monthly: list[MonthlyCashflow]
    cf_quarterly: list[QuarterlyCashflow]


@dataclass
class EngineState:
    """Everything the pipeline produced, handed to the summary in one bundle."""

    inputs: DealInputs
    acreage: Acreage
    land: Land
    infra: Infrastructure
    allocation: list[LotAllocation]
    project_months: int
    ledger: InfrastructureLedger
    sections: SectionSchedule
    lot_revenue: LotRevenue
    pods: PodRevenue
    av: AssessedValue
    mud: BondProceeds
    wcid: BondProceeds
    op: Operating
    dmf: list[float]
    dmf_total: float
    contingency: list[float]
    contingency_total: float
    rev_monthly: list[float]
    cost_monthly: list[float]


def _sum(series: list[float]) -> float:
    return sum(series[1:])


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_outputs(s: EngineState) -> Outputs:
    costs: Costs = s.inputs.costs
    infra = s.infra
    sec = s.sections
    lr = s.lot_revenue
    op = s.op

    # Unrounded totals used for ratios.
    total_revenue = (
        lr.total_base
        + lr.total_premiums
        + lr.total_escalation
        + lr.total_fence_fees
        + lr.total_marketing_fees
        + s.mud.total
        + s.wcid.total
        + s.pods.total_residential
        + s.pods.total_commercial
    )
    landscaping_total = (
        sec.total_landscaping + infra.total_detention_landscaping + infra.total_road_landscaping
    )
    dry_utilities_total = sec.total_urd + sec.total_streetlights + op.road_streetlight_total
    streetlight_total = op.road_streetlight_total + sec.total_streetlights
    infra_cost = (
        infra.total_plants
        + infra.total_amenities
        + infra.total_detention
        + infra.total_detention_landscaping
        + infra.total_other
        + infra.total_roads
        + infra.total_road_landscaping
        + sec.total_dev_cost
        + sec.total_landscaping
        + sec.total_fencing
        + sec.total_urd
        + streetlight_total
        + lr.total_site_work
    )
    legal_total = costs.legal_monthly * op.legal_end
    insurance_total = costs.insurance_monthly * op.insurance_end
    gross_costs = (
        s.land.escalated_total
        + infra.total_plants
        + infra.total_amenities
        + infra.total_detention
        + sec.total_dev_cost
        + infra.total_other
        + infra.total_roads
        + sec.total_fencing
        + dry_utilities_total
        + lr.total_site_work
        + landscaping_total
        + legal_total
        + _sum(lr.taxes)
        + op.mud_total
        + insurance_total
        + op.marketing_total
        + _sum(lr.brokerage)
        + _sum(lr.closing)
        + _sum(lr.mailboxes)
        + op.prof_svc_total
        + s.contingency_total
    )
    personnel_total = (
        costs.personnel_monthly * op.personnel_end
        + costs.marketing_personnel_monthly * op.marketing_personnel_end
    )
    bookkeeping_total = costs.bookkeeping_monthly * op.bookkeeping_end
    receivables_total = s.mud.total_fees + s.wcid.total_fees
    below_line = s.dmf_total + personnel_total + bookkeeping_total + receivables_total
    total_cost = gross_costs + below_line
    gross_profit = total_revenue - gross_costs

    # Displayed lines, rounded to the dollar.
    revenue = RevenueLines(
        lot_sales=round(lr.total_base),
        mud=round(s.mud.total),
        wcid=round(s.wcid.total),
        premiums=round(lr.total_premiums),
        fence_fees=round(lr.total_fence_fees),
        escalations=round(lr.total_escalation),
        marketing_fees=round(lr.total_marketing_fees),
        residential_pods=round(s.pods.total_residential),
        commercial_pods=round(s.pods.total_commercial),
        total=0,
    )
    revenue.total = (
        revenue.lot_sales
        + revenue.mud
        + revenue.wcid
        + revenue.premiums
        + revenue.fence_fees
        + revenue.escalations
        + revenue.marketing_fees
        + revenue.residential_pods
        + revenue.commercial_pods
    )
    cost_lines = CostLines(
        land=round(s.land.escalated_total),
        plants=round(infra.total_plants),
        amenities=round(infra.total_amenities),
        detention=round(infra.total_detention),
        sections=round(sec.total_dev_cost),
        other=round(infra.total_other),
        roads=round(infra.total_roads),
        fencing=round(sec.total_fencing),
        dry_utilities=round(dry_utilities_total),
        site_work=round(lr.total_site_work),
        landscaping=round(landscaping_total),
        legal=round(legal_total),
        lot_taxes=round(_sum(lr.taxes)),
        mud_hoa=round(op.mud_total),
        insurance=round(insurance_total),
        marketing=round(op.marketing_total),
        brokerage=round(_sum(lr.brokerage)),
        closing=round(_sum(lr.closing)),
        mailboxes=round(_sum(lr.mailboxes)),
        professional_services=round(op.prof_svc_total),
        contingency=round(s.contingency_total),
        total=0,
    )
    cost_lines.total = sum(v for k, v in cost_lines.model_dump().items() if k != "total")
    btl = BelowTheLine(
        dmf=round(s.dmf_total),
        personnel=round(personnel_total),
        bookkeeping=round(bookkeeping_total),
        receivables_fees=round(receivables_total),
        total=0,
    )
    btl.total = btl.dmf + btl.personnel + btl.bookkeeping + btl.receivables_fees

    gross_margin = revenue.total - cost_lines.total
    total_cost_rounded = cost_lines.total + btl.total
    net_margin = gross_margin - btl.total

    operating = OperatingDetail(
        marketing_total=round(op.marketing_total),
        marketing_per_month=round(op.marketing_per_month),
        marketing_final_period=op.marketing_personnel_end - 1,
        prof_services_total=round(op.prof_svc_total),
        prof_services_per_month=round(op.prof_svc_per_month),
        prof_services_final_period=op.personnel_end - 1,
        general_personnel_total=round(costs.personnel_monthly * op.personnel_end),
        general_final_period=op.personnel_end - 1,
        marketing_personnel_total=round(
            costs.marketing_personnel_monthly * op.marketing_personnel_end
        ),
        marketing_personnel_final_period=op.marketing_personnel_end - 1,
        legal_total=round(legal_total),
        legal_final_period=op.legal_end - 1,
        mud_hoa_total=round(op.mud_total),
        mud_hoa_monthly=round(costs.mud_monthly),
        mud_hoa_final_period=op.mud_end_period,
        insurance_total=round(insurance_total),
        insurance_final_period=op.insurance_end - 1,
        bookkeeping_total=round(bookkeeping_total),
        bookkeeping_final_period=op.bookkeeping_end - 1,
        dmf_total=round(s.dmf_total),
    )

    # Per acre and per lot, on unrounded figures.
    total_lots = sum(lot.total_lots for lot in s.allocation)
    dev_acres = s.acreage.residential_developable if s.acreage.residential_developable > 0 else 1.0
    amenities_per_lot = (
        (infra.total_amenities + landscaping_total + sec.total_fencing) / total_lots
        if total_lots
        else 0.0
    )
    active = [lot for lot in s.allocation if lot.on]

    # Cash flow range: extend past the project length if bonds or revenue land later.
    last_cf_month = s.project_months
    for m in range(s.project_months + 1, MAX_MONTHS + 1):
        if s.rev_monthly[m] > 0 or s.cost_monthly[m] > 0:
            last_cf_month = m

    cf = [s.rev_monthly[m] - s.cost_monthly[m] for m in range(1, last_cf_month + 1)]
    closing = s.inputs.tract.closing_date
    if closing:
        irr = xirr(cf, cashflow_dates(closing, last_cf_month))
    else:
        irr = monthly_irr(cf)

    # Peak cash need and breakeven from cumulative net cash flow.
    cumulative = 0.0
    peak_need = 0.0
    peak_month = 0
    breakeven_month: int | None = None
    for m, net in enumerate(cf, start=1):
        cumulative += net
        if cumulative < peak_need:
            peak_need = cumulative
            peak_month = m
            breakeven_month = None
        elif cumulative >= 0 and breakeven_month is None and peak_need < 0:
            breakeven_month = m

    summary = Summary(
        unlevered_irr=irr,
        total_revenue=revenue.total,
        gross_costs=cost_lines.total,
        gross_margin=gross_margin,
        gross_margin_of_revenue=_ratio(gross_margin, revenue.total),
        gross_margin_of_costs=_ratio(gross_margin, cost_lines.total),
        below_line_total=btl.total,
        total_cost=total_cost_rounded,
        net_margin=net_margin,
        net_margin_of_revenue=_ratio(net_margin, revenue.total),
        net_margin_of_costs=_ratio(net_margin, total_cost_rounded),
        return_on_cost=_ratio(gross_profit, gross_costs),
        total_lots=total_lots,
        lot_supply_18mo=round(sum(lot.lots_18mo for lot in active)),
        home_sales_per_year=round(sum(lot.pace for lot in active) * 12),
        project_length_months=s.project_months,
        project_length_years=round(s.project_months / 12, 1),
        developable_acres=round(s.acreage.developable, 2),
        residential_developable_acres=round(s.acreage.residential_developable, 2),
        rev_per_dev_acre=round(total_revenue / dev_acres),
        cost_per_dev_acre=round(total_cost / dev_acres),
        infra_per_dev_acre=round(infra_cost / dev_acres),
        gm_per_acre=round(gross_profit / dev_acres),
        infra_per_lot=round(infra_cost / total_lots) if total_lots else 0,
        amenities_per_lot=round(amenities_per_lot),
        lot_av=round(s.av.lot_av),
        comm_av=round(s.av.commercial_av),
        peak_cash_need=round(-peak_need),
        peak_cash_month=peak_month,
        breakeven_month=breakeven_month,
        breakeven_year=(breakeven_month - 1) // 12 + 1 if breakeven_month else None,
    )

    wf_land = cost_lines.land
    wf_sections = cost_lines.sections + cost_lines.site_work + cost_lines.mailboxes
    wf_infra = cost_lines.plants + cost_lines.detention + cost_lines.roads + cost_lines.other
    wf_amenities = cost_lines.amenities + cost_lines.fencing + cost_lines.landscaping
    wf_other = cost_lines.total - wf_land - wf_sections - wf_infra - wf_amenities
    waterfall = Waterfall(
        revenues=revenue.total,
        land=-wf_land,
        sections=-wf_sections,
        infrastructure=-wf_infra,
        amenities=-wf_amenities,
        other=-wf_other,
        gross_margin=gross_margin,
    )

    # Yearly table: rounded per year, cumulative from the rounded nets so the table foots.
    final_year = max(math.ceil(s.project_months / 12), 1)
    last_year = max(final_year, (last_cf_month - 1) // 12 + 1)
    yearly: list[YearlyRow] = []
    running = 0
    for year in range(1, last_year + 1):
        months = range((year - 1) * 12 + 1, min(year * 12, MAX_MONTHS) + 1)
        rev = sum(s.rev_monthly[m] for m in months)
        cost = sum(s.cost_monthly[m] for m in months)
        net = round(rev - cost)
        running += net
        yearly.append(
            YearlyRow(
                year=year,
                revenue=round(rev),
                cost=round(cost),
                net=net,
                cumulative=running,
                lots=round(sum(sec.lot_deliveries[m] for m in months)),
                homes=round(sum(s.av.home_sales[m] for m in months)),
            )
        )

    landscaping_m = [s.ledger.landscaping[m] + sec.landscaping[m] for m in range(0, MAX_MONTHS + 1)]
    dry_m = [
        sec.urd[m] + sec.streetlights[m] + op.road_streetlights[m] for m in range(0, MAX_MONTHS + 1)
    ]
    cf_monthly: list[MonthlyCashflow] = []
    for m in range(1, last_cf_month + 1):
        categorised = (
            s.ledger.land[m]
            + s.ledger.plants[m]
            + s.ledger.amenities[m]
            + s.ledger.detention[m]
            + s.ledger.other[m]
            + s.ledger.roads[m]
            + sec.dev_cost[m]
            + landscaping_m[m]
            + sec.fencing[m]
            + dry_m[m]
            + lr.site_work[m]
            + s.dmf[m]
        )
        cf_monthly.append(
            MonthlyCashflow(
                month=m,
                year=(m - 1) // 12 + 1,
                revenue=round(s.rev_monthly[m]),
                cost=round(s.cost_monthly[m]),
                net=round(s.rev_monthly[m] - s.cost_monthly[m]),
                rev_lot_sales=round(lr.revenue[m]),
                rev_res_pods=round(s.pods.residential[m]),
                rev_comm_pods=round(s.pods.commercial[m]),
                rev_mud_wcid=round(s.mud.revenue[m] + s.wcid.revenue[m]),
                cost_land=round(s.ledger.land[m]),
                cost_plants=round(s.ledger.plants[m]),
                cost_amenities=round(s.ledger.amenities[m]),
                cost_detention=round(s.ledger.detention[m]),
                cost_other=round(s.ledger.other[m]),
                cost_roads=round(s.ledger.roads[m]),
                cost_sections=round(sec.dev_cost[m]),
                cost_landscaping=round(landscaping_m[m]),
                cost_fencing=round(sec.fencing[m]),
                cost_dry_utilities=round(dry_m[m]),
                cost_site_work=round(lr.site_work[m]),
                cost_dmf=round(s.dmf[m]),
                cost_operating=round(max(0.0, s.cost_monthly[m] - categorised)),
            )
        )

    cf_quarterly: list[QuarterlyCashflow] = []
    for q in range(1, (last_cf_month - 1) // 3 + 2):
        months = range((q - 1) * 3 + 1, min(q * 3, last_cf_month) + 1)
        rev = sum(s.rev_monthly[m] for m in months)
        cost = sum(s.cost_monthly[m] for m in months)
        cf_quarterly.append(
            QuarterlyCashflow(
                quarter=q,
                year=(q - 1) // 4 + 1,
                quarter_of_year=(q - 1) % 4 + 1,
                revenue=round(rev),
                cost=round(cost),
                net=round(rev - cost),
            )
        )

    return Outputs(
        acreage=s.acreage,
        land=s.land,
        infrastructure=infra,
        lots=s.allocation,
        revenue=revenue,
        costs=cost_lines,
        below_line=btl,
        operating=operating,
        summary=summary,
        waterfall=waterfall,
        yearly=yearly,
        cf_monthly=cf_monthly,
        cf_quarterly=cf_quarterly,
    )
